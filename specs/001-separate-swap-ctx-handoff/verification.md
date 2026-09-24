# Implementation Verification Record

Status: **INCOMPLETE — LIVE UNVERIFIED**. A written implementation, reviewed
slice, or passing fake test is not full acceptance. `tasks.md` remains the
implementation task authority; this document identifies the evidence needed
to close the feature against its approved, explicitly versioned contracts.

## Latest checkpoint — thirteenth Bite 4 INCONCLUSIVE; T050 architecture APPROVED; offline gate PASS

The user authorized exactly one thirteenth Bite 4 run. Sol reviewed and froze
the command; it exited 2 after about 20 seconds with overall
`INCONCLUSIVE`, `bite5_decision=pending-review`,
`production_disposition=unsupported`, and `support_claim=false`. The positive
arm was INCONCLUSIVE with `effect-or-observer-uncertain`,
`observer_complete=false`, `cleanup_complete=false`, and
`release_candidate_ready=false`. The negative arm was not run; its reasons
were `positive-release-candidate-not-established`,
`positive-cleanup-incomplete`, and `positive-observer-incomplete`. No target
container was created. Quarantine found zero labeled containers and removed no
volumes; two unattached labeled volumes, one source-state and one target-state,
remain preserved. No replay of the thirteenth run or cleanup is authorized.
The one-run fourteenth diagnostic authorization and its pending post-push Sol
preflight/command review and required command seal are recorded below.

The source container was observed running after the source phase, then stopped
and removed. The target-state volume was created, after which source-report
schema validation failed before copy, release, or target-container creation.
The sealed artifacts do not retain the inner source exception. The unbound
`parent_uuid` reference in the legacy/source runtime initializer is a
deterministic static cause candidate, not a directly proven historical
exception. The sealed manifest SHA-256 is
`5815a42167d5a772131368264111f9cb124f726fe33e101dee318eb3f8bd9d23`; sanitized
stdout is `cd94d74854d88431c178b17b8893179e34b8821034e4570f02986051a86f374a`,
private source report is
`55d8311397fa473ee85612ea0e95c60ce6aa0caee074d2f360632964b6ab146e`, and the
abort ledger is
`b898eabb9f181fdcbf8a0c00d11f36090417d9ad62059bc8a183072d8ba557a8`. Runtime
pins were SDK 0.2.153, CLI 2.1.273 with SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`, and
immutable image SHA-256
`a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094`. No event
indices were present in sealed artifacts.

T050 is a future-only offline correction. It removes the unbound initializer,
adds allowlisted component/function/line-only `error_site` metadata to generic
fallbacks, and persists the exact returned source report in a private,
append-once bounded envelope with invocation/container/report digests directly
after `_runtime_exec` and before source stop/removal or target-volume
creation. Schema, phase, support claim, target reach, and source bindings are
validated before progression. Malformed/fallback reports produce the fixed
public `source-runtime-report-invalid` INCONCLUSIVE result through quarantine
while retaining private evidence. An otherwise-valid explicit
`target_code_reached=true` remains FAIL; absent or unknown reach evidence
remains INCONCLUSIVE. Astra approved T050. Sol's canonical focused gate passed
427 tests, 2,168 deselected, zero failures; JUnit SHA-256 is
`f887c8d09ccfd49c1a59165b2cf59c4102d108d1655821382266e38267619633`. The user
has since authorized exactly one fourteenth full diagnostic run, pending push,
Sol's post-push preflight/command review, and the required command seal. Do not
run before these are complete.
This authorization grants no cleanup or deployment authority and does not
establish production support or decide Bite 5.

## Historical checkpoint — T049 architecture APPROVED; scoped gate PASS

Astra approved the T049 diagnostic-only architecture. Sol's expanded canonical
scoped gate passed: 420 passed, 2,168 deselected, zero failed. The selected
diagnostic was ready for a separately authorized runtime test; that offline
gate did not grant authorization. The existing `strict-v1` default remains
unchanged. At that checkpoint the twelfth Bite 4 run remained historical
INCONCLUSIVE with `startup-task-event-observed`; the later thirteenth
authorization and result are recorded above. Bite 5 remains pending and
production remains unsupported.

Frozen T049 source hashes are native probe
`0469e76f6d8755b5e77f242d9faaa02e0a503df0410338d4205f4109085a0c68`, two-domain
harness `35353d2546fd57c0f0967062f0e2a0afdbe69b6fe47645ef7246b1dfa8da285f`,
loopback tests `518d28013a68e24b71ff7a51f68a7a1267a5046f49d1ace56dd03d79c4412b6a`,
and T049 harness tests
`30aafebe54dd1c91176ace94d81138c3cacc0e56544f6882f3b8ae252376ee3a`. The
420-test scoped JUnit, stdout, and stderr digests are respectively
`0cab98c25f027f1997a41fa46c70aa33657e2bad4249484590d94d183542a56c`,
`8ae52e932ce0cc549343cfd3b98f6e1524784d005f43601f845456178481090c`, and
`ff8cafb88544fd8aea6f652c617812d975ceb22443788fbfa82a957e96d317cc`.

The full repository suite ran once: 2,560 passed, 28 failed, zero skipped,
five warnings, in 3,951.61 seconds. It used the pre-fix loopback test hash
`f2580cd01a347390a51242a088ed72766999fc56ca404624708eca5e640ee947`; the ten
stale loopback fixtures have since been fixed and the expanded scoped gate is
green. Fourteen native context/restoration failures hit the unchanged
unsupported controller gate. Of the other four failures, an isolated
three-node rerun passed the CLI unsafe-parent and daemon-route cases, while the
CLI persistent-lifecycle case still failed on an ownership conflict; the shell
aggregate was not rerun. The full-suite JUnit digest is
`48e559aaffe2078dc550bdfaf48792b338577b1cf50baa8827b736943f960a2f`; the
isolated three-node rerun JUnit digest is
`828f1b9277375ad703cd07d5f5f6400d080bb5d18ca27c2143b08c0c959291b1`. The full
suite has not been rerun after the fixture fixes. These results do not
establish a green full suite, a baseline cause for the remaining failures, or
a runtime-conclusive Bite 4.

## Thirteenth full Bite 4 run — INCONCLUSIVE; one-run authorization consumed

The full-run public report selected explicit release but granted no support
claim. The positive arm stopped after source stop/removal and target-state
volume creation because the source runtime report did not match the expected
source-phase schema. The source process was observed running after its phase,
then stopped and removed. There are no event indices in the sealed artifacts.
Copy, release, target launch, and negative-arm execution were not reached. The
failure is INCONCLUSIVE rather than FAIL because no specific runtime contract
violation was established from the retained report; its inner source exception
was not retained. Static review identified the unbound `parent_uuid`
initializer as a deterministic cause candidate only. The source correction is
future-only and does not rewrite this run.

The preserved inventory is zero labeled containers and two unattached labeled
volumes (one source-state and one target-state). No cleanup, retry, or
fourteenth authorization occurred. Exact artifact hashes, runtime pins, and
negative-arm conditions are in the latest checkpoint above. Bite 5 remains
pending and production remains unsupported.

## Historical runtime checkpoint — post-twelfth-run cleanup complete; Bite 4 INCONCLUSIVE; Bite 5 pending

The separately authorized twelfth full Bite 4 invocation ran once and exited
2. Its sanitized report uses schema
`openrepotools-bite4-two-domain-report/v1`, with
`diagnostic_status=INCONCLUSIVE`, `bite5_decision=pending-review`,
`production_disposition=unsupported`, and `support_claim=false`. The positive
arm is inconclusive with reason `startup-task-event-observed`,
`observer_complete=true`, `release_candidate_ready=true`, and
`cleanup_complete=false`; the negative arm did not run.

The T048 source terminal seed was available. Source stop event 34 and target
stop event 151 were harness/engine enforced with exit 137 and `oom=false`;
source removal was event 36. Exact copy verification was event 92, and
pre-release custody event 119 reported `exact_match=true`. Durable release,
launch intent, and target create were events 120, 121, and 123. Target removal
was event 153, final helper removal was event 179, and event 180 persisted
final custody. Target initialization was bound to the same source parent UUID.
One complete stopped `system/task_notification` matched session/task; optional
agent/tool identity was unknown and its event UUID differed from the source parent.

The gate recorded `successful_result_seen=true` and
`history_query_allowed=false`; `history_query_sent=false` and
`read_complete=false`, with no query or read sent. No
parent/child startup messages were observed. The terminal-correlation-only
event does not prove replay or that no new execution occurred, and there is no
loaded-history proof. Final custody retained the saved edit and linked source
parent-history prefix. The target parent JSONL grew from 52,825 to 55,372 bytes
and `other_config_mutation_count=1`, so this custody result does not establish
whole target-tree immutability.

The generic negative-arm reason `positive-release-candidate-not-established`
is misleading: `release_candidate_ready=true`, and the actual unmet
prerequisite was `cleanup_complete=false` after the INCONCLUSIVE run's
resources were preserved. This does not change the negative arm's `not-run`
status.

The sealed result digest is
`4289f073b7c8508633f13c829d0ed670c813f917480ff106bd0525d14ee24294`. Frozen
source hashes are native probe
`cec4b4f5010e4e9c56c08492b1a12692689b8160ba0f213b779adc75e44819dc`, harness
`bb5161ba852aaa7f83c314d171b3929dcbca07c106b8899ee514f085ee111a77`, and
tests `eb462ac654390785bc45fd0e84b0b1f675dc539c6ea89e62bc95c5e0db65c29b`.
The run used SDK `0.2.153`, CLI `2.1.273` with SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`, and
Docker client/server `29.8.1`/`29.6.2`.

Runtime artifact SHA-256 values:

| Artifact | SHA-256 |
| --- | --- |
| Input artifact | `70c0bbff9e65bfaa3a5e668bab0daf3858084755128cf0797560e37fde0475b7` |
| Private command artifact | `5129bfccefd7b1436fe22c3d507bbc731170725214ba0ed7d4e6808f24dcef17` |
| Stdout | `7b89fa542e6865d6bcf8301dfa8919acddee6ae2fb5de6bbb43f591af4bb2cb2` |
| Sanitized report | `13264ba136af4e85c7dd3939546c52469c6887743dad454b578ab4fa1c1f210f` |
| Arm result | `21dc04c163dd68ad30898238820257afbdab11cbcbe0bb8e37846f5d6274ce89` |
| Empty stderr | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Artifact manifest (36 entries) | `36a2c41c89c804e0dfd2a884eae4f6ac38d4c90d1cec4049d4f0d19d7de82c7b` |

The restricted evidence bundle contained 37 files (including the manifest),
16 directories, no symlinks, file mode 0600, and directory mode 0700. The
parsed public report and stdout JSON matched; the report contained no detected
raw UUID, path, or run label. The preserved engine inventory is 19 volumes
(12 source-state, seven target-state), four older stopped Bite 4 containers
plus one stopped
metadata diagnostic container, zero running containers, and no current target
container; this is the pre-cleanup inventory observed for the sealed run. After
separate explicit authorization, Sol High completed exact allowlisted cleanup
on 2026-09-24. Preflight found 19 labeled local diagnostic volumes (12
source-state, seven target-state) and five stopped containers (four Bite 4,
one read-only metadata diagnostic), with no running containers or unrelated
attachments. Postflight confirmed all 24 allowlisted resources absent. The
sealed bundle and all 36 manifest entries are unchanged; no prune, evidence
deletion, or unrelated removal occurred. The private mode-0600 allowlist
artifact SHA-256 is
`d6ea783b66a4bee326ee23b83d80a82797f2f633db19831b131b0ac4cd0a4d78`. The
twelfth run authorization is consumed. At that historical checkpoint no
thirteenth attempt was authorized; the later one-run authorization and result
are recorded above. Bite 4 remains INCONCLUSIVE, Bite 5 remains pending, and production remains
unsupported. Astra confirms that the sticky gate behaved as specified; the
absent Bite 3 OS witness and all-path restart fence prevent a PASS or
production claim.

## Historical checkpoint — T048 architecture/offline PASS; eleventh runtime INCONCLUSIVE

T048's bounded callback/task-tool mismatch handling and SDK-sidecar identity
bridge passed Astra's final architecture review and Sol's formal offline gate.
Sol ran
`tests/run.sh --parallel-safe -k 'two_domain or native_task or native_hook or hook_ack or source_terminal_seed'`:
243 selected tests passed, 2,270 were deselected, and there were zero
failures/errors/skips. Frozen SHA-256 values:
native probe `cec4b4f5010e4e9c56c08492b1a12692689b8160ba0f213b779adc75e44819dc`,
test module `eb462ac654390785bc45fd0e84b0b1f675dc539c6ea89e62bc95c5e0db65c29b`,
and harness `bb5161ba852aaa7f83c314d171b3929dcbca07c106b8899ee514f085ee111a77`.
Formal T048 artifact SHA-256 values are: collection
`faccee4f683353b8b045ca4cabcde9577dc21a1b940b29d507c238ba8a28c303`,
collection stderr
`258d41b4b0c044e6cca80eef34923db708a89381a2b2a46f68b22fa20c6e7839`, stdout
`3b07ba258bc296c94bf7821c273fa484d916d59e8fd2f8e1d87361324f337924`, stderr
`5777718cd72f663c66e07c986b898d7cbb20a60fdb16fcd7413ad28bfa68d448`, JUnit
`8dccdf14e7d332638b5e8d54a906d490e6744f57826d8c1729448e843113b113`, and
pre/post hash-file `a098b8811734559984d5bda556730ea03283d9a9a348d3e2e75c295476bab662`.
No host-absolute artifact path is recorded here.

The separately authorized eleventh Bite 4 run was executed once and exited 2,
INCONCLUSIVE with `startup-task-event-observed`. Its authorization is
consumed. The T048 offline pass does not change or upgrade any historical
runtime result. Seventeen volumes (11 source-state, six target-state), five
older stopped containers, zero running containers, and zero current target
containers remain preserved. No cleanup, retry, or twelfth attempt is
authorized. Bite 4/Bite 5 remain open and production remains unsupported.

### Eleventh full Bite 4 runtime — executed once; INCONCLUSIVE

The v3 source seed was available through the SDK-sidecar proof and the source
projection set `release_candidate_ready=true`. Source stop/removal was
harness/engine enforced with exit 137; exact copy, pre-release custody, and
final custody were preserved. Durable release, target launch-intent, and
target-create records occurred at events 120, 121, and 123. The target harness
stopped/removed with exit 137. One complete stopped target
`task_notification` matched session/task; optional agent/tool identity remained
unknown and the UUID differed. The sticky startup gate skipped the history
query after observing the task event. No parent/child startup messages were
observed; the negative arm did not run. This is INCONCLUSIVE under Bite 3 and
does not prove loaded history or production containment.

Event 180 records final custody. The sealed result digest is
`9403d9910279ec0c6f047f53dc4d1c672751e90bb63d637985803c8202f04e5f`. The
private evidence bundle is identified as
`openrepotools-bite4-eleventh-preflight.YKJSLl` (35 files mode 0600; 16
directories mode 0700). Runtime artifact SHA-256 values:

| Artifact | SHA-256 |
| --- | --- |
| Input artifact | `439d6f044995bc84d5f73ae905970e9f64fbaca4f81871698cf530f0ffd718b0` |
| Stdout | `f47cb555d77747029072db22e63fba03d57b37e0d1e582d684057446d3ed6f04` |
| Sanitized report | `0220f77e4d0f5a6b98e0e06f5f2bbc1bf23117c548215eac0637ecc43fcb1e21` |
| Arm result | `5b19526a07fc5100e0cb33dec785fe14191c3de601e41d66ab4be09936da6320` |
| Empty stderr | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The preserved engine inventory is 17 volumes (11 source-state, six
target-state), five older stopped containers, zero running containers, and no
current target container. No cleanup, retry, or twelfth run occurred or is
authorized. Astra's post-run assessment is that the sticky gate behaved
correctly under Bite 3; no replay or loaded-history proof was observed. The
next step is read-only protocol investigation and separate governance if a
progression-rule change is proposed.

## Historical checkpoint — T047 offline PASS; tenth runtime INCONCLUSIVE

T047's bounded source-native terminal-seed repair passed Astra's final
architecture review and Sol's formal offline gate. Frozen SHA-256 values:
native probe `86470ec387152debb46e507ba5e325117bf23d29e41808a65ad967654bfe0586`,
harness `bb5161ba852aaa7f83c314d171b3929dcbca07c106b8899ee514f085ee111a77`,
and tests `5b417c029a7ab3ed934d1787069c6965ccd4acf3a345bdf5d80a2144286c21e4`.

Sol ran
`tests/run.sh --parallel-safe -k 'two_domain or native_task or native_hook or hook_ack or source_terminal_seed'`:
210 selected from 2,480 collected; 210 passed, 2,270 deselected, zero
failures/errors/skips, in 13.02s. The private temporary artifact bundle
`openrepotools-t047-offline.rA7s0z` was mode 0700. SHA-256 values: stdout
`ec7e33e0d3f55753f594cd1c4b9c027d989a0db32bb0587218ef8ebc0288bb50`, stderr
`11e3656d6e5fd8889282c3d6e5700459b11db45aa0cc1071bac1e2470e49fb8f`, final
collection `c7280e86e115ce135c5d6d3bbb8b7c7f17e18629c832676af2aceca0c951f370`,
and pre/post hash-file `6d1ec8f6b9b49c89d278b369c87aa8ebe5202167abc2c7b3c0a41776a58d74c9`.
No JUnit digest was supplied. Luna's separate focused development smoke passed
207 tests with 2,273 deselected; it is not the formal gate.

At the T047 checkpoint, the separately authorized tenth Bite 4 attempt had
run once and exited 2 with an INCONCLUSIVE result. The tenth authorization was
consumed; no cleanup or eleventh attempt had yet been authorized. That
restriction is historical; the current one-attempt authorization appears in
the latest T048 checkpoint above. The offline gate and runtime observation do
not establish production containment.

### Tenth full Bite 4 attempt — executed once; INCONCLUSIVE

The positive result reason was
`source-native-task-terminal-seed-unavailable`, with detailed reason
`terminal-task-hook-evidence-incomplete`. The lifecycle v2 projection retained
four complete events: one started task with a tool-use ID, and one hook
callback rejected as `hook-tool-use-id-mismatch`; zero hook callbacks were
stored or joined. The source stop/removal was harness/engine enforced with
exit 137, not natural graph shutdown. Exact copy, pre-release identity-linked
history custody, and final saved-edit/history-prefix custody were retained.
No release or target-launch ledger, target runtime container, or positive
release candidate was established; the negative arm did not run.

The event ledger covers events 1–145; event 146 persists the final result with
sealed digest
`addefcf9282109879c5fd1eaa74a199eb03949e8b81ed8c13b4728a837db8258`.
Inventory is 15 preserved volumes (10 source-state, five target-state), the
same five older stopped containers, zero running, and no tenth-run container.
No cleanup occurred.

Tenth-run artifact SHA-256 values:

| Artifact | SHA-256 |
| --- | --- |
| Private exact-input digest | `c03ce448efa8b305bb76da9dfe5cd376e2cbae15bb121374e37bd0a92f90038f` |
| Sanitized report | `f759c4a570a5cb3f37d762dc1805d53a7d731c964ab8e151efdc66d3cd6a30e5` |
| Stdout | `dab4a30620c9bb78c55a59770ad9e541739169877102b3639b5b914c85de0909` |
| Arm-result artifact | `c78bb531f2ca3a0b6d026c3e974e847f18ac6ff7007594ab93d7a2f4e321e409` |

Stderr was empty. The private py-bench evidence bundle is identified as
`openrepotools-bite4-tenth-preflight.7EHz5N`; its directories were mode 0700
and files mode 0600. No host-absolute artifact path is recorded here.

Astra's post-run interpretation is that the hook mismatch rejection was
correctly fail-closed. The pinned SDK only forwards an optional callback tool
ID and does not guarantee that it equals the selected task's tool ID. Because
the retained summary omits the rejected hook event kind and associated
digests, the evidence cannot distinguish a different tool role, task, or
association. This is not evidence of a CLI defect. Any future investigation
should retain bounded rejected-hook kind/order and separate callback, input,
current-task, session, and tool digests, then seek an authoritative structured
bridge. Do not relax exact equality or infer a join from cardinality. At that
historical tenth-run checkpoint, an eleventh attempt was not yet authorized.

## Historical checkpoint — ninth Bite 4 run; INCONCLUSIVE

The one authorized ninth full Bite 4 attempt ran once and exited 2 with a
sanitized public report whose `support_claim` is false. The positive arm is
INCONCLUSIVE with reason `source-native-task-terminal-seed-unavailable`,
`observer_complete=true`, `release_candidate_ready=false`, and
`cleanup_complete=false`. The negative arm was not run; a positive release
candidate was not established.

Source stop/removal, exact source-to-target copy, identity-linked pre-release
parent-history custody, and final custody of the copied volumes were observed.
The source parent exited and tracked fixtures were excluded, but
source-container shutdown was harness/engine enforced with exit 137. This is
not natural graph shutdown or production containment evidence. The source
projection reported the terminal seed unavailable but omitted the detailed
unavailable-reason envelope, so the exact missing identity/event condition is
unknown. The target-state volume was copied; there was no release or
target-launch ledger and no target runtime container.

The observer ledger covers events 1–145. Public event 146 is
`final-custody-result-persisted` and carries sealed arm-result digest
`982c9efb8b22b97d78e5eac557834523bb542edf7bc6dec5928bed93445a7aeb`. This
sealed digest is distinct from the arm-result artifact digest and the
pre-release custody digest below. T046's available-seed transfer, target
fingerprint validation/correlation/startup/history query, and negative arm
remain unexercised. The offline closure remains valid. Bite 5 remains pending;
production remains unsupported.

Current inventory is 13 volumes (nine source-state and four target-state),
five older stopped containers (four Bite 4 and one metadata diagnostic), zero
running, and no ninth-run container. No cleanup or retry occurred. The
ninth-run authorization was consumed at that checkpoint; no tenth attempt
was then authorized, and no cleanup occurred.

Frozen source hashes: harness
`b0f01d529771eab2d7ebd1738b8702e25bfc2b9fc446e7236548088cad63338e`, native
probe `1042153b8f768f1bce772bc42d3f923b3d05d7a3fb944070c5327b7b5624c77d`, and
tests `d4242957190624b76d652457bd9b0376e99d3d2985820666021845356b016c33`.
The selected SDK was 0.2.153, selected CLI 2.1.273 with SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`, and
immutable image
`sha256:a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094`.

Ninth-run artifact SHA-256 values:

| Artifact | SHA-256 |
| --- | --- |
| Private preflight exact-input digest | `f2700df1e1c3bb515628bbb321482dd2a3d41f6e129dd5e3319798ce5b221411` |
| Sanitized public report | `ba0d4bff43ff68dcae0331766daa82e5e554ddc6f75d83664c8c59c19c3a8430` |
| Stdout | `8e2d1a7af7958af3bca894783abd99f30b1698f7d052eb4603724455ea24d071` |
| Empty stderr | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Arm-result artifact | `dd53208829c62bfc951ff563205eb2118169a86edf6c46fb15646c1ec8ff9972` |
| Source-stop ledger | `0abab1d9f8fa0963651bcca0997ab57cb0d4bac54a2191b5dd09f5761cf54343` |
| Source-removal ledger | `fce8e002e8bc5636c59710f5759c26f317d14e64923e6e31c28b8429e6d89dd1` |
| Source-container stop record | `a4059c65e7af7c558e418fc2bdddd6f420d06fbea086166b78585f0168d3dee9` |
| Embedded source manifest | `1e13464eb9f664079240230d243d97233c3dda278e6953fe022dd040ee1ac585` |
| Pre-release custody | `e1efcf62a0cb22bdb3c968e64271c938a32a49e9f1428dd4b33bf74b0ce0bf0c` |
| Sealed arm-result digest in event 146 | `982c9efb8b22b97d78e5eac557834523bb542edf7bc6dec5928bed93445a7aeb` |

The restricted artifact set contained 27 files and 16 directories; files were
mode 0600 and directories mode 0700. Raw paths and runtime IDs remain in the
private evidence store.

## Historical checkpoint — eighth Bite 4 run; INCONCLUSIVE

The single user-authorized eighth full Bite 4 attempt ran once with the
T043/T044-hash-guarded command in `runbook.md`. The outer process exited 2 and
the sanitized public report is INCONCLUSIVE; the corrected image-ID sanitizer
passed. The positive arm is INCONCLUSIVE with
`startup-task-event-observed`, `observer_complete=true`,
`release_candidate_ready=true`, and `cleanup_complete=false`. The negative arm
did not run.

The run observed source stop/exclusion, exact source-to-target copy,
pre-release identity-linked parent-history custody, durable release,
exact-parent target initialization/start/stop/removal, and final saved-edit
and history custody. The bounded target startup snapshot recorded one
`system/task_notification`, status `stopped`, provenance `target-observed`,
sequence 1, and matching session correlation. Task/agent identity remained
unknown, source terminal seed was unavailable, and identity was unresolved;
the snapshot is unknown/incomplete. No assistant/tool activity, parent/child
messages, or gateway routes were observed. The sticky history-query gate
correctly skipped its query because the startup task event was observed. This
does not satisfy Bite 3's PASS criteria and is not a Bite 5 verdict.

The run added two preserved volumes. Current inventory is eleven volumes
(eight source-state, three target-state), four older stopped Bite 4 containers
plus one stopped metadata diagnostic container, zero running, and no
eighth-run containers. No cleanup or retry occurred. The eighth authorization
is consumed; no ninth run or cleanup is authorized. Production remains
unsupported.

Frozen hashes used for the attempt: harness
`a3852a6969599c1b605edb60a371069d6de9f41317a9082cd69c0e65ab800c62`, native
probe `bf7032097ba264aa199e6f0555d4ab4412c85043b0b12e674a8a4461722d78e9`, and
tests `c23f6a3d91aafc33dd056b67d89034363c7ba6ecea494389b519b6897fd698fd`.
Private artifact SHA-256: manifest
`3626f45bdea3b9932b5debbf7e946df7ad7ed5a47a83f552caf47334ba88ddd4`, public
report `eba9d0dc0646697af4f453d6881d95d3055d97935a8d53b070ea034cfaee5383`,
stdout `ae51147de5c27869769f49a9e715864f9f3cff3d2be78fff9b36e2d938cfaba3`, arm
result `641242a7fe2625e0b978463d7a3c7aabab4bf3b053378d665e564ae89929be32`,
release ledger `fcc6faabe0b0446dcf5cef5d763b17b9587c13e74798ed90eaeebd5709246e6c`,
and target-launch ledger
`808af1888b195193807600ad8192c43123888da1d7f1f79a1904e4fc475dfe60`. Raw
paths and runtime IDs remain in the restricted evidence record.

## Historical checkpoint — T042 seventh run; arm INCONCLUSIVE, public report packaging FAIL

The single user-authorized seventh full Bite 4 attempt ran once with the
reviewed T041-hash-guarded command. The outer command exited 1 because report
packaging raised `private-identifier-in-report`: `args.image` was the immutable
image ID and the report intentionally publishes that same value at
`identities.image_id`. Sol and Astra confirmed that this is a sanitizer false
positive, not a runtime identity violation. The private positive arm remains
INCONCLUSIVE with `startup-task-event-observed`; the negative arm did not run.

The positive arm observed source stop/exclusion, exact source-to-target copy,
pre-release identity-linked parent history custody, durable release, target
startup/stop/removal, and final custody. The exact parent UUID matched. One
native task event occurred at target startup, so the sticky gate skipped the
history query; no parent/child messages, history read failure, or protocol
errors were observed. `release_candidate_ready` was true and
`cleanup_complete` false. This is not PASS under Bite 3 and does not decide
Bite 5.

The attempt added two preserved volumes and left no seventh-run container.
At that checkpoint inventory was nine engine volumes (seven source-state, two
target-state) and five older stopped containers, with zero running. No cleanup
or eighth attempt was authorized at that checkpoint. Private artifact SHA-256: manifest
`537b3741de9c42e6ba9428f343d22a68e3196556e3755107a0c468f4e756902e`, public
report `3db0840883f58d5dfd88fe727cb29e0df7e8977cd7c126f84ffdffb7dee025e9`,
stdout `e2ef15dee6b3b6884d6d36fb1d237d3ff862be6448a055512650ad683683bbed`, arm
result `6cee6803105e5668c166a340660624d99050e5df292f5c3b939502c2c0df30c5`,
release ledger `44d97078a835f12ddb7931f4e79778ed81a4da34f22df5efd4f71ce1fbd80807`,
and target-launch ledger
`8024b9967ee5f20fc5a103e6b191cc81f91f7c974f0d2e4301266a8e0db4a6f8`.
The 37 private artifact files were mode 0600; raw paths and runtime IDs remain
in the restricted evidence record.

The future-only sanitizer correction retains `args.image` and the resolved
image ID in the private-value set, validates a full resolver-matched
`sha256:<64 hex>` value, and masks only `identities.image_id` in a copied scan
projection. The generic private-value check is unchanged. The target runtime
also emits a bounded detached startup task-lifecycle snapshot after the initial
read and before any optional history query, with `target-observed` provenance
and unavailable source-seed provenance. The sticky gate inputs and refusal
branch are unchanged. Astra's integrated architecture review passed. Sol's
canonical `tests/run.sh --parallel-safe -k two_domain` gate passed **151 tests,
0 failures/errors/skips in 9.749s**, including the 14 metadata cases. Frozen
hashes are harness
`a3852a6969599c1b605edb60a371069d6de9f41317a9082cd69c0e65ab800c62`, native
probe `bf7032097ba264aa199e6f0555d4ab4412c85043b0b12e674a8a4461722d78e9`, and
tests `c23f6a3d91aafc33dd056b67d89034363c7ba6ecea494389b519b6897fd698fd`.
Private gate artifact SHA-256: stdout
`a02ce67b08de9dfe3a363fba88e6f9bda1115a9559cc1d294bc2e6f9ef2f05bf`, stderr
`d6e0c18bc312a3a3e5e716b798c52292f5a23568cebabee3b20ea8c487be42e5`, JUnit
`d77e2bae637e5ae217d42cf74f6de4396f855a013c7b200885c8375f759eb470`.
This is future-only offline evidence; it does not change the seventh run's
underlying INCONCLUSIVE arm, repair its public artifact, or validate a runtime.
It did not itself authorize an eighth run; the separate eighth authorization
and result are recorded in the latest checkpoint above.

## Historical checkpoint — T040 metadata scan and T041 offline gate PASS

Sol executed the separately authorized stat-only scan against the sixth
attempt's preserved source-state volume. The diagnostic exited 0 and reported
nine files, 14 directories, and 394,590 total file bytes. The largest
identified file was a config `.json` of 306,896 bytes. The scanner read no file
contents. The selected volume was mounted read-only; its contents remain
unchanged while engine attachment metadata changed for the new diagnostic
container. Current inventory is seven engine volumes and five stopped
containers, zero running. The diagnostic container/artifacts remain preserved;
there was no cleanup or repeat.

Private artifact SHA-256: manifest
`aa3c4c235afa931507b6dedd28939e43e97c1cd212901c48c7d2150ec016499d`, public
JSON `af7b84e3145e6596044d767c164ca0ddec573ae25c93a1d2ba886de96f22ab68`, and
private JSON `c0f0b0a74d970562782cff6106aeb29fdf1d4b6768d70798c2e34a65df29e0f2`.
The exact scanner and runner hashes are in `runbook.md`; raw paths, names, and
IDs remain in Sol's restricted evidence record.

T041 now separates fixture-tree byte limits from history evidence: the
candidate uses 512 KiB per fixture file and 2 MiB per complete tree, with
`MAX_HISTORY_CONTENT_BYTES` unchanged at 64 KiB and
`MAX_HISTORY_SCAN_BYTES` unchanged at 512 KiB. Manifest, copy/re-manifest,
pre-release/final custody, and target prestart all use the same tree defaults.
Synthetic regressions cover the measured large JSON through exact copy,
manifest, pre-release and final custody; exact and cap+1 file/aggregate
bounds; and refusal of an oversized history prefix. Astra's formal architecture
review passed. Sol's canonical `tests/run.sh --parallel-safe -k two_domain`
gate passed **144 selected tests, 0 failures/errors/skips in 14.434s**. Frozen
hashes are native probe
`a0379e325db46d599d5e3d98c3b25f4200036ae8e08eb1a618d43d59d4f5b069`, harness
`9f8a71fe30e370e6569bf7db2ec2466cb9338ca8aa89a001f39215a32f1de28c`, and
tests `fa29dffec7c86131152dcee8b116e02f2a772130177d3d4fb25cb406a915b6b5`.
Private gate artifact SHA-256: stdout
`cecc5ecbbd849fe2a7ae66e63728eaf45fbc7a580130c3a553fe472af2283356`, stderr
`e8e31f13e4582ffc1e0a2ce36474cdd0547620d2020024e5c8e9af934dfe9847`, and
JUnit `a4d994ae3288ceb50023edb79e408e22d73954c7664aa2e3f12a4ec0386ff8a8`.

At this T041 checkpoint, one seventh full Bite 4 attempt was authorized after
the review, offline gate, and fresh preflight passed; exact-command review was
still pending. The run is recorded in the current T042 checkpoint above.

## 2026-09-23 historical checkpoint — T036/T037/T038 offline PASS; fifth run INCONCLUSIVE

Astra's targeted T036 and T037 reviews passed. T036 adds a frozen trusted
startup wrapper that takes two bounded `/proc/self/mountinfo` captures for
source, every helper, and target. The external observer binds each capture to
the exact container/image/run/role/start identity and engine create/start
evidence before uploads and again before SDK/helper work. Parsing checks the
controlled mount destinations, effective mount and superblock options, exact
sizes, ancestor overmounts, duplicates, completeness, and bounds. Attach
transport remains tracked through verified stop. Unsafe policy findings are
FAIL only after identity/event binding and durable capture; malformed or
uncertain evidence is INCONCLUSIVE and prevents further work. T037 preserves
volumes and sanitized leftovers on normal FAIL/INCONCLUSIVE returns and
uncertain finalization; cleanup requires fully successful custody.

Sol's frozen `tests/run.sh --parallel-safe -k two_domain` gate passed **110
tests, 2,293 deselected**. Frozen SHA-256 hashes:

- `tests/probes/managed_two_domain.py`:
  `6a459bbf647f1d4bca463cc0c3eadfe7c377fe955c8059deeaea032fc9fbdb5f`
- `tests/probes/managed_native_loopback.py`:
  `e8b876e7322579067fb0903513fc33358c496d110c3bcaf25cb481b440979287`
- `tests/test_lane_managed_loopback_probe.py`:
  `faccfdd533d39c5f91730446320e2b9f8850850d295b7f4d20c6b495922dbfce`

The T036/T037 gate is offline only; it does not establish the Bite 3
production producer. The fifth full Bite 4 attempt was executed once and
ended INCONCLUSIVE before source start because Docker inspect reported
`StdinOnce=true` while the T036 host validator expected false. No wrapper,
SDK, history, custody, release, or target ran. The new Created source
container and attached source-state volume were preserved. Total inventory is
five source-state volumes and three stopped source containers (two Created,
one Exited 137), zero running; no cleanup/retry occurred. Full sanitized
result and artifact digests are in `live-validation.md`.

## T038 interactive-stdio correction — reviewed; offline gate passed

The future-only T038 correction pins the Docker-created wrapper profile as
`OpenStdin=true`, `AttachStdin=true`, `Tty=false`, and `StdinOnce=true` in both
host wrapper checks and the native active-witness validator. The harness keeps
one tracked attach across both challenge stages; EOF/transport loss refuses
without reconnect or replay. Host diagnostics now distinguish image-ID
mismatch from wrapper-configuration mismatch. The strict `StdinOnce` value
matches Docker CLI's `--interactive` configuration
([`opts.go`](https://github.com/docker/cli/blob/master/cli/command/container/opts.go)).

Astra's targeted review passed. Sol's frozen `tests/run.sh --parallel-safe -k
two_domain` gate passed **127 tests, 2,293 deselected in 10.07s**. Frozen
SHA-256 hashes:

- `tests/probes/managed_two_domain.py`:
  `9f8a71fe30e370e6569bf7db2ec2466cb9338ca8aa89a001f39215a32f1de28c`
- `tests/probes/managed_native_loopback.py`:
  `7454e747791ddfb45f9d506b1a2999d6df5f4c714dcb064cf7be0dffb8db9d22`
- `tests/test_lane_managed_loopback_probe.py`:
  `c143d192c9efcbb1e7dc9591047f8307ba87cd9abdec35e7ed82df1a08154fea`

Private gate artifact digests: JUnit
`288eee4d45f4f0f7e281b578935518d30339eaeba7c220db000739e12eceb14c`, stdout
`a389bcb58b3a4801fca1704dffa992a6af4cf075699663a62088b6180339ef91`, stderr
`2cc91d3ad93459e516f0b35eb81793b2bc43b25c18242c24966c7bf72113469c`, and
log `077579550ba653f7559c9c74ee8d443ea95014d55c7d1180996e1b5b5bef2048`.
These offline artifacts remain in the restricted executor record.

## Sixth-run preflight, command review, and runtime result

Sol's new preflight passed for SDK 0.2.153, selected bundled CLI 2.1.273 with
SHA-256 `6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`,
local image ID
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`,
and Docker client/daemon 29.8.1/29.6.2. It verified the reserved private
parent is mode 0700, the experiment child is absent, the exact-input record is
mode 0600, and pinned SDK, Docker socket, and frozen source are visible inside
`py-bench`. It created no runtime object. The exact interpreter, private
parent path, and raw runtime identities remain in Sol's restricted record.
The distinct command in `runbook.md` passed Sol's outer and nested `bash -n`
checks before execution. The outer block
SHA-256 is `29b64b76dd70659b5db62ddfb7227508f2579ca14f276df3d898fe7624bfb08a`;
the nested body SHA-256 is
`97a4d5a7e849dcb0bbef1624fe78d5cc6407c68e9da0e9ead972962b371f861f`. Root GO
was issued and Sol ran the command once. Preserve all earlier resources. No
cleanup or further runtime is authorized.

The sixth full Bite 4 attempt exited 2 with **INCONCLUSIVE**. The source SDK
phase returned; the observer recorded source running and then source stop and
removal with durable intents. Target-state volume creation occurred only after
source removal. The first custody COPY helper failed its metadata manifest
scan at `_manifest_summary(args.source)` with Docker exec exit 1 and
`RuntimeError: two-domain file size limit exceeded` at the configured 64 KiB
per-file bound. This occurred before verified copy, pre-release history
custody, durable release, target-container creation/start, or negative arm.
The positive arm was `effect-or-observer-uncertain` plus
`quarantine-container-preserved-for-custody-review`; the negative arm was NOT
RUN (`positive-release-candidate-not-established`). Quarantine stopped and
preserved the COPY helper. Two run-owned volumes (source and target state) and
one Exited helper were preserved. Aggregate inventory is seven volumes (six
source-state, one target-state) and four stopped containers (two Created, two
Exited), zero running. No cleanup or retry occurred. The sixth authorization
is consumed, no seventh full Bite 4 attempt is authorized, Bite 5 is pending, and production is
unsupported. The exact oversized relative path awaits read-only diagnosis;
do not infer a history mismatch or inspect/mount the preserved volume
writably.

Private SHA-256: report
`2cca888a2b65170087c500432a7c7a6c26eacdd58509dff3774b8c0ae05db84d`, stdout
`ccc773ab9cbc36157388e32d232cbe2b4305be249082d81ab900c92ec9d3eb9d`, empty
stderr `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
abort ledger `d0e98156493112d2b17642c5fee39cc41efb46f3bcaf4b315ffe22a0147d6121`,
and private artifact manifest
`7711540cb5e09a7f5ccb4be6e61658624ba4086efde827ddbdb93c0902e2e25e` (16
files independently matched; mode 0600). Machine-specific paths and raw IDs
stay in Sol's restricted record.

The proposed follow-up is a separate stat-only metadata candidate, not a
seventh full Bite 4 attempt. Scanner offline, Astra architecture, Sol command,
and fresh read-only preflight gates have passed. It has not been authorized or
run.
`tests/probes/inspect_two_domain_volume_metadata.py` scans only the sixth
attempt's source-state volume through a proposed read-only, volume-nocopy
mount, never reads evidence file contents, and reports relative paths only in
private output. A separate public projection validates and removes paths. The
candidate deliberately reports files above 65,536 bytes and large aggregate
size instead of rejecting them; this does not widen the custody helper's
existing limit. Candidate hashes and operator protocol are in `runbook.md`.
No resource was changed for this candidate.

## T040 metadata diagnostic candidate — preparation checkpoint (historical)

Sol ran the scanner-only selector `tests/run.sh --parallel-safe -k
two_domain_metadata`: **14 passed, 2,420 deselected in 5.94s**. This gate
covered synthetic metadata fixtures only; it did not call Docker or inspect a
volume. Scanner and test hashes were unchanged before and after the gate:

- `tests/probes/inspect_two_domain_volume_metadata.py`:
  `fbff3be87a288501d64d977e91d37ba01f5bb43ad596e211e1ca691ea9f81c39`
- exact scanner source embedded in the proposed Docker `Config.Cmd`:
  `abbe57cc78fdfe4b613df7c421af8447b10fa00bd4edd4ff0c21c4f3029dc683`
- `tests/test_two_domain_metadata_diagnostic.py`:
  `110d007b80c262536c2c0a1d3d39e2e35981735b96e12b05a381c76a7d48e49c`

Private output digests: stdout
`1c8829ae7060d1f65193f5c6d4ba55d7091a205aa52da7f7e983536b2bce2f7f`, stderr
`b1c681ff340ae5c55c6132ed809a2c27d9e092b7e25df9e33e0645ee98f9aa12`, and
JUnit `d3cd1b85cd9a597a18a25491a6303896a8f30bfdac334eb2c9e1fdbdc985d7de`.
Astra's architecture review and Sol's exact command review passed; the outer
and nested shell checks and all six Python heredoc parses passed. Fresh
read-only preflight verified seven labelled volumes, four stopped containers,
zero running attachments, the selected source volume's expected local
driver/labels/options, and no diagnostic container. This remains preparation
only: no runtime authorization has been given and no Docker create/start/stop
or volume scan occurred. Bite 4 remains INCONCLUSIVE and Bite 5 remains
pending.

Sol's reviewed command hashes: outer block
`fb0b719fe8df74d2f7eee5ed8c04fe3f81a4384204f1b100034799347c75df2f` and nested
body `c518a912e6310c505cb73483f5b0d8aa9751a59c40e161d5be5d46688d082be4`.

## T033 future-only observer correction — architecture reviewed; offline gate passed

Astra's targeted architecture review passed the future-only Docker volume
observer correction. The correction requires a nonempty `Actor.ID`, rejects a
conflicting top-level `id`, and does not infer identity from volume attributes.
Before release, it waits for exact planned mount/unmount counts with a bounded
timeout and checks both independent event streams for health before snapshot.
Sol ran `tests/run.sh --parallel-safe -k two_domain`: **39 passed, 2,293
deselected in 9.47s**. JUnit SHA-256:
`91b1b34dc62cf8e34035eea99b6bbdb37b3675518f1585fa469f220be580c6ba`; log
SHA-256:
`b62a03373d1fd2950579083ab6275d8b720143e8b7d5f4f9495fa5dcd1ec467e`.

- `tests/probes/managed_two_domain.py` SHA-256:
  `1aa5f6f35beea569aa6c4f206cb7dcd08f9ee9d4cdea1bee5bc268ef34cd06b6`
- `tests/probes/managed_native_loopback.py` SHA-256:
  `4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695`
- `tests/test_lane_managed_loopback_probe.py` SHA-256:
  `5f5869655cc046674dbd697e3f816fd28ea66e38c0f4a0203225d1695d5e2bca`

Private JUnit/log artifacts remain in the restricted execution record; no
private path or raw runtime identity is copied here. This is an offline-only
gate for the future observer repair. It did not call Docker or the SDK, did not
retry Bite 4, did not inspect or clean the preserved volume, and does not
runtime-verify the repair. At the T033 checkpoint Bite 4 still had only the original INCONCLUSIVE
pre-source result; the separately authorized follow-up and later create-only
smoke are recorded below. Bite 5 remains pending and production remains
unsupported.

## Newly authorized Bite 4 follow-up — INCONCLUSIVE at source-container creation

After T033's offline correction, the user explicitly authorized one new
bounded Bite 4 runtime. This was a distinct follow-up, not a replay of the
original aborted invocation. Sol's fresh read-only preflight passed for SDK
`0.2.153`, CLI `2.1.273` (SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`), and
local image ID
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`.
Astra's read-only assessment found no concrete blocker: the first attempt had
not launched or stopped a source, and its preserved volume had no attached
containers. The old volume remained outside the new run's identity set.

The corrected volume observer progressed past volume create, but Docker
source-container creation failed with exit 125. The exact daemon stderr was not
retained, so the cause is unconfirmed. Sol's read-only diagnosis found a
moderate-to-high-confidence candidate command-builder defect: a writable
`--mount type=volume` contains an explicit `rw` token. This is an inference,
not confirmed daemon output. Astra agrees the correction should be future-only
and offline-verified before any further runtime can be considered.

The host harness exited 2 with `INCONCLUSIVE`, `support_claim=false`, and
production unsupported. The positive arm had
`release_candidate_ready=false`, `observer_complete=false`, and
`cleanup_complete=false`; the negative arm was NOT RUN. No source container or
SDK/runtime started, and no source history, release, target, or startup event
was produced. There were zero run-labelled containers and two preserved
`source-state` volumes (one from each distinct attempt). No cleanup or retry
occurred. The outer stderr file is empty (SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`), but the
exact daemon create error is absent.

The consumed command and frozen hashes are in `runbook.md`; the separate
run's artifacts are documented in `live-validation.md`. SHA-256: stdout
`794f6e7e954cf5bd2a39da185878ab6c42754e18c64c0f3cc6d91e01ded7350f`, report
`08ab7467fe46d4ef1bf3a53216ff67b86fcdb8e3ed40913ccc03aba0ef273a96`, abort
ledger `9dff73fb5cd0b7f2adf9d6a3e089359efa74d64709233a26ead37fc5998defb7`,
and quarantine `b6cd550366b186fd3166561ef3b00875d664efc555ba152705ff6414dbea6e3e`.
The frozen harness/helper/test hashes remain unchanged at
`1aa5f6f35beea569aa6c4f206cb7dcd08f9ee9d4cdea1bee5bc268ef34cd06b6`,
`4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695`, and
`5f5869655cc046674dbd697e3f816fd28ea66e38c0f4a0203225d1695d5e2bca`.
At the T033 checkpoint, no third runtime had yet been authorized. The later
third attempt and result are recorded below. Production remains unsupported.

## T034 future-only Docker mount/error-report correction — reviewed; offline gate passed

Astra reviewed and passed the future-only correction. The isolated two-domain
command builder omits an access token for writable engine-volume mounts and
uses only readonly for read-only mounts. Docker failure stderr is capped at
4,096 retained bytes and its exit status is written only to the private,
mode-0600 arm-abort ledger as base64; the public report remains sanitized.
Astra's stated limits are retained: subprocess capture itself is unbounded,
and timeout or pre-arm failures do not use this stderr-recording path. This
corrects future diagnostics only; it does not confirm the cause of the prior
Docker exit 125.

Sol ran tests/run.sh --parallel-safe -k two_domain in py-bench: 41 passed,
2,293 deselected in 9.09s. The first candidate gate had 40 passed and one
failed because a redundant assertion expected /source instead of the actual
final token dst=/source; the exact mount-string assertions passed. The
assertion was corrected and Sol reran the frozen selector successfully. JUnit
SHA-256: edb34b8404e20b3e8815e1b17a9b12f2b4347bfc1a75c6b1cebb0183cf552963;
log SHA-256: 9376fd78c8c29678af02aefaa57c38d73bbefc7d0cf4bf0290fbe2d82e72b1f0.

Frozen candidate SHA-256 values are harness
c5c183cb215ecf56f3ff028dd2e4175364a1d7f2720df6fcff29e9baadc7cdac, shared
probe/helper 4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695,
and tests
3f7c5f63af5331d7bdc4116b04535bc6f549bb852b05a68cef318b115ab9e1ac.
Private JUnit and log paths remain in Sol's restricted evidence store. No
Docker command, SDK runtime, cleanup, or further Bite 4 attempt ran during this
correction. The executed runtime candidate hashes in runbook.md and
live-validation.md remain historical. At this T034 correction checkpoint Bite 4 was not completed and no third
runtime had yet been authorized. The later single third-attempt authorization
and result are recorded below; no cleanup or Bite 5 verdict is authorized.

## 2026-09-22 T034 isolated Docker-create smoke — narrow PASS

After the T034 offline correction passed review and tests, the user separately
authorized one isolated Docker-create smoke. Sol used the exact frozen
_container_create_command source variant (harness SHA-256
c5c183cb215ecf56f3ff028dd2e4175364a1d7f2720df6fcff29e9baadc7cdac) with the
pinned local image ID
sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d.
Docker created one fresh run-labelled container with one fresh labelled
engine-managed volume. Independent inspection confirmed Created state,
Running=false, and the writable volume mount RW=true. The container was never
started; no SDK/runtime or network activity occurred.

Sol removed only this smoke-owned container and volume, then independently
verified both were absent. The two pre-existing source-state volumes were
untouched, and zero run-labelled containers remained. This PASS establishes
only that the current builder's create specification is accepted and has the
expected writable mount. It does not confirm that the earlier exit-125 failure
was caused by its former rw token because the exact prior daemon stderr was not
retained. It is not a Bite 4 source/target experiment and did not change the then-current
Bite 4 INCONCLUSIVE results or pending Bite 5 decision. At that smoke
checkpoint no third full runtime had been authorized; the later one-run grant
and result are recorded below. No cleanup or Bite 5 verdict is authorized.

Private evidence SHA-256 values: commands
f6136e05ab0e834d41682e655c41c79f005d88786aaae5347f7806819badd517; inspect
5cad66170547b9a015dbbf2abd2791210f7bcb2b8718e6fe3f384deb3de7be0d; cleanup
3f15320367ab36900f00fe8e3ac19e292ab96081018b70556265077c90ba50d3. Raw
container/volume IDs and private paths remain in Sol's restricted record.

## Third full Bite 4 run — INCONCLUSIVE before source startup

The user authorized one third full Bite 4 attempt after Astra's read-only
pre-run assessment and Sol's fresh preflight passed. Sol used T034 frozen
hashes: harness c5c183cb215ecf56f3ff028dd2e4175364a1d7f2720df6fcff29e9baadc7cdac,
helper 4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695,
and test 3f7c5f63af5331d7bdc4116b04535bc6f549bb852b05a68cef318b115ab9e1ac.
The harness exited 2 with INCONCLUSIVE before source startup.

The newly created source container inspected as Created, Running=false, Pid=0,
with Docker's exact unset-time sentinel `0001-01-01T00:00:00Z` for both start
and finish. HostConfig.Tmpfs listed exactly /tmp
and /opt/loopback, but Mounts listed only the writable /opt/state volume.
The validator raised two-domain tmpfs destination mismatch because it
prematurely required configured tmpfs to appear as active Mounts entries.
Quarantine then refused to remove the never-started container because no die
event was available, reporting quarantine-die-event-unconfirmed. The source
container and its volume were preserved; the two older volumes remain
untouched. Total engine inventory is three labelled source-state volumes and
one run-labelled Created source container. No SDK/runtime, history, release,
target, negative arm, cleanup, or retry occurred. The positive arm was
effect-or-observer-uncertain; the negative arm was NOT RUN. This is not a Bite
5 verdict. The third authorization is consumed; no fourth run is authorized.

Private hashes: abort ledger
ff62f4fa6026ef1bf3af4cf5af5b5bcacb322e809ce7c198265770e25ce50388;
quarantine
8c55e5d370934f22c612fb5e0cb126a023979349f131fcce551c3173c6c1848e;
report
e95ab2c945d6048cc454b32f0d949d8d65082ea65cf633c321e311289d6419cc;
stdout
34eea213ed27b67ee5ecf99a7dc1162e6fa6e35b2308a66265a8f6417c2a022d; empty
stderr
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.
Raw IDs and exact private paths are kept only in the restricted execution
record.

## T035 future-only correction — architecture reviewed; offline gate passed

The opt-in two-domain candidate now has a strict Created-state predicate that
accepts Docker's exact zero-time sentinel (`0001-01-01T00:00:00Z`) only with
Created, Running=false, and Pid=0. Before start, the validator accepts the
exact configured tmpfs profile when Docker omits tmpfs from active Mounts and
the expected state volume is the only mount. The start wrapper inspects and
revalidates immediately after `docker start`, before any SDK/helper exec; a
running record without tmpfs Mounts evidence refuses. Failure quarantine
preserves a corroborated never-started Created container without waiting for a
die event, while a recorded start attempt or observed start event remains
uncertain.

Focused regressions cover the exact Docker sentinel and rejected missing,
null, empty, and malformed time values; partial/extra/conflicting mounts;
running-without-tmpfs refusal before exec; and confirmed versus ambiguous
Created-state quarantine. Astra's targeted architecture review passed. Sol ran
the canonical `tests/run.sh --parallel-safe -k two_domain` selector in
`py-bench`: **59 passed, 2,293 deselected in 6.74s**.

Frozen SHA-256:

- `tests/probes/managed_two_domain.py`:
  `cb026d5e31ec7e619934b0bbba28e9f2a7ccad124c20c06b07938d6c7f9ec0dd`
- `tests/probes/managed_native_loopback.py`:
  `efac7b5ead8a9e61061058b55fba9679b8d6a926e8874118cea06401b9b71ea5`
- `tests/test_lane_managed_loopback_probe.py`:
  `f89b12b6a5906a4627c07f2fd5142d424ed46a16c9b74bd48a8ff30b5068f11b`

Private gate artifacts: JUnit
`0c54381c4e908e2852428d9283208e31c44310efc51fed2a48d6b141e34d4e3a`,
stdout `643ad7f52573d4d473e2b3e52a9f4c3e9649015251507213230dcab6389a1386`,
and stderr
`9106fc921eb50718d353a772621be8258951e030e543fc2d35f512ae0a9b7407`.
This is an uncommitted future-only diagnostic correction and offline gate; it
does not runtime-verify Bite 4 or establish the Bite 3 producer. At the time of
this gate no later runtime had occurred; the separately authorized fourth
attempt is recorded next.

## Fourth full Bite 4 run — INCONCLUSIVE before any container exec

The user-authorized fourth run used the frozen T035 harness/helper/test hashes
above, pinned SDK 0.2.153 / CLI 2.1.273, and the immutable local image. It
exited 2 with `INCONCLUSIVE` after the source container started. The first
post-start `validate_two_domain_isolation` in `_install_observer_files`
rejected Docker inspect `Mounts` because active `/tmp` and `/opt/loopback`
tmpfs entries were missing, despite `HostConfig.Tmpfs` listing those exact
configured destinations. It failed closed before any `docker exec`, CLI/probe
copy, SDK/runtime, source history, release, target, or negative arm.

The positive arm reported `effect-or-observer-uncertain`,
`release_candidate_ready=false`, `cleanup_complete=false`, and
`observer_complete=false`, with quarantine reason
`quarantine-container-preserved-for-custody-review`. Quarantine stopped the
new source container and preserved it as Exited 137 with its attached new
source-state volume. The three old volumes and old Created container were
untouched; the first two old volumes are unattached, and the third remains
RW-referenced by the old Created container. Current inventory is four
source-state volumes, two source containers (one Created, one Exited 137), and
zero running containers. Nothing was removed; no cleanup or retry occurred.
The fourth authorization is consumed; no fifth attempt is authorized. Bite 4
remains INCONCLUSIVE, Bite 5 is pending, and production is unsupported.

Astra confirms the fail-closed result is correct: missing active Mounts
evidence is not proof tmpfs is absent. Future evidence requires exact-container
mountinfo or a reviewed trusted pre-SDK attestation; do not relax the validator
silently.

Private SHA-256: stdout
`2b09daf7efac84ba5386ab5578cfe14da3ec76bc1ddc415fc4d9835180dffc4c`, empty
stderr `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
abort `7a1c95d9bfb92cd3cf427f495626c6d39cd7e0a60043b3742db7c8a93e07ca8b`,
quarantine `f44acfbe54965a6bc8a2f15ee186122ceced3a19c7286d014e11f6e0c505338a`,
stop `635884ddb9445b6bc297e9ba1967b75b3097f9fafecf0be5a7fbc96ffb5ab79a`,
manifest `8bd8faa64245210d6c8a7cd2ac801e0798a300852f87a51f25aa640fd931cb80`,
and report `45a92030725db92a51c3f84b92ebd97561b8b7e2b40d8117f1162ca92a7c82f0`.
Raw paths and IDs remain private.

### Fourth-run root-cause and blocker audit — historical pre-T036/T037 checkpoint

The observed failure is an evidence mismatch, not proof that tmpfs was absent.
T035's exception applies only to an independently confirmed never-started
`Created` container. The running-state branch in
`tests/probes/managed_native_loopback.py:3538-3544` still requires each expected
tmpfs destination to appear in top-level Docker `Mounts`. In the fourth run,
`HostConfig.Tmpfs` contained the exact `/tmp` and `/opt/loopback` configuration,
while top-level `Mounts` omitted both. Docker CLI issue
[#3974](https://github.com/docker/cli/issues/3974) documents that `--tmpfs`
uses the `HostConfig.Tmpfs` field separately from the top-level `Mounts`
representation used for bind and volume mounts. That API split explains why
the inspect fields can differ; the missing `Mounts` entries do not settle
whether the active mounts existed. The fourth run failed this deterministic
first post-start check before any container `exec`. The same validator and
start sequence serve source, helper, and target containers, so this is a
shared role blocker; the helper and target roles were not reached in that run.

**T036 is the next technical gate.** Keep the check fail-closed and add a
bounded witness from a frozen trusted startup wrapper, read before any SDK or
helper work. It should read `/proc/self/mountinfo` in the container's own
mount namespace; the [Linux kernel proc documentation](https://www.kernel.org/doc/html/v6.9/filesystems/proc.html#proc-pid-mountinfo-information-about-mounts)
defines its mount-point, per-mount-option, filesystem, and superblock-option
fields. The external observer must bind the witness and digest to the exact
container ID, image digest, run identity, and start epoch. Validate the exact
role-specific tmpfs destinations, effective access and execution options,
size bounds, and duplicate absence. Require a second fresh witness before the
SDK/helper handoff as well. Missing, oversized, stale, duplicate, or ambiguous
evidence refuses; `HostConfig.Tmpfs` alone is never an active-mount waiver.

**T037 is also required before another run can be considered.** Read-only
control-flow review found normal `fail`/`inconclusive` arm returns that still
call `_remove_run_volumes`: the pre-release gate at
`tests/probes/managed_two_domain.py:2353`, the unproven negative-refusal path
at `:2465`, and the final target result path at `:2680`. The design contract
requires a failed arm to preserve stopped containers and all volumes for
manual custody review (`contracts/source-only-diagnostic.md`, “On any failed
arm”). Make every normal `fail` or `inconclusive` return persist its bounded
result and preserve run-owned volumes; only a fully successful custody path
may cross the cleanup boundary. Add focused offline cases proving those
failure paths do not request deletion or record cleanup complete, alongside a
successful-custody boundary case.

No source SDK/history/custody/release/target phase was exercised after the
post-start check, so this audit establishes no later runtime failure. Startup
event/history-query concerns remain conditional, and the separate Bite 3
production producer is still absent. At this earlier audit checkpoint, four
source-state volumes and two source containers were preserved, and no fifth
runtime or cleanup was authorized. Subsequent T036/T037/T038 work and fifth-
run history appear in the dated sections above; Bite 5 remains pending and
production remains unsupported.


## Bite 4 two-domain harness — offline gate passed; pre-source abort

Sol High ran the frozen focused offline selector
`tests/run.sh --parallel-safe -k two_domain`: **26 passed, 2,293 deselected**.
JUnit SHA-256 is
`3ed1d389eca432b5101303e816b1a26879aa928e448da3f2790315621e81c8c1`; log
SHA-256 is
`1b4fd09ad4ba87db6ac717a31bd1f9b402c47e9cee5e5127e8a1bdd37a3e403d`.
Private artifacts are retained in Sol's restricted artifact store; its path is
kept in the private execution record.
This is focused offline evidence only. The test gate made no Docker or SDK
runtime calls. Sol's separate read-only runtime preflight passed. The later
host harness invocation exited INCONCLUSIVE before starting the selected SDK
source phase; the bounded Bite 4 source/release/target experiment did not occur.
Bite 4 is **NOT COMPLETED** and Bite 5 remains pending.

- `tests/probes/managed_two_domain.py` SHA-256:
  `e092869a765cee41987f4be0d1019ab8223f1ede37814d52c543709d78bf3354`
- `tests/probes/managed_native_loopback.py` SHA-256:
  `4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695`
- `tests/test_lane_managed_loopback_probe.py` SHA-256:
  `33349e8a3349fff06a51816ea938cc5305996baacfc407ec7713dfcd464e9c28`

This historical 26-test offline result applies to the preceding probe/test
hashes; T033's later 39-test run above covers the future-only observer repair.
Neither offline result is a Bite 4 runtime observation, establishes production
containment, or changes `support_claim=false`.

The separate read-only runtime preflight selected SDK 0.2.153 / CLI 2.1.273
(CLI SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`) and
verified local image `py-bench:brett` as immutable image ID
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`.
The resolved SDK interpreter and private artifact paths are in Sol's private
preflight record. The bounded runtime invocation is in `runbook.md`.

The initial outer-shell setup failed before the harness because interpreter
and private-directory variables expanded empty; no experiment effect occurred.
The corrected command launched the harness once. It exited 2 with report
`INCONCLUSIVE`, `support_claim: false`, and production disposition
`unsupported`. The positive arm stopped on
`effect-or-observer-uncertain`; the abort ledger reported no externally
observed volume-create event. Read-only diagnosis found exactly one volume
create event in the engine history window, with its actor ID matching the
preserved `source-state` volume, but event attributes contained only the
driver, not custom run/role labels. A label-filtered `docker events` query
therefore returned no event, although a current volume inspection showed the
expected labels. This establishes an observer/filter mismatch on this engine;
it does not establish that Docker omitted volume creation.

The run left zero run-labelled containers and one labelled `source-state`
volume, preserved for manual review. No source SDK runtime/history, release,
target, or startup ran; the negative arm was not run. Quarantine removed zero
resources, cleanup was false, and observer completion was false. No cleanup of
the preserved old volume is authorized. The read-only diagnosis is complete: the volume event
history had one create event whose actor ID matched the preserved volume, but
the event attributes exposed only the driver. A run-label-filtered event query
returned no rows despite current inspection confirming the labels. The
diagnostic `INCONCLUSIVE` report is not the Bite 5 verdict. Astra's targeted
architecture review of the offline correction passed. A later user
authorization for one distinct follow-up and Astra's read-only pre-run
assessment are recorded above; the follow-up awaits Sol's execution. This does
not authorize cleanup or further retries. Details and artifact hashes are in
[`live-validation.md`](live-validation.md). No Bite 5 decision has been made.

## Bite 2 frozen opt-in hook diagnostic — 2026-09-22

`--observe-native-hooks` is explicit and default-off. The focused probe records
bounded sanitized SubagentStart/Stop facts with neutral once-only ACKs; null or
pre-task joins remain partial/unresolved, while mismatched events, sessions,
tool IDs, stale/reused agents and malformed input refuse. Hook facts do not
promote task terminal/effect state, bypass the sticky startup guard, or add a
history query; `support_claim=false` remains invariant.

Sol's red baseline was 8 new failures, 137 passed, 2,140 deselected; the
frozen green result was **153 passed, 2,140 deselected, 9.22 seconds**. The
approved parallel-safe exception was diagnostic-only because six unrelated
pytest processes blocked serialized entry; this is not the full release gate.
Probe SHA-256 `b02ca7ec99f4cfca5aee44e31ac74739d7cffb12ee5f4c8cfb650968f5884a35`;
test SHA-256 `bc1de523aabd0bf4ecad08ebd3c2329481778d8e03cdf8ad97499a4bd48ad763`;
JUnit `e7e2cf93fb07cbfab408ab469cc9944fe1aa07a200dcff54320ef4b854888667`;
manifest `f1541fb387325dc15ffabf11f46d9babc7f958bdd98bebf79d6ac83bf0e22395`;
private artifact basename `openrepotools-sol-bite2-green.Fn1pT3`.

No runtime test, production change, account activation, commit, or push was
performed. This proves only partial/local hook correlation. The hook-to-history
sidecar bridge and real-runtime observation remain **UNVERIFIED**; no stored
fact is treated as loaded context. Astra reviewed and passed the Bite 3
containment/restart definition below. This historical note predates the Bite 4
two-domain design and offline gate recorded above; the bounded runtime is now
pending separately. The current producer still does not supply Bite 3's
containment/restart proof, so production remains unsupported regardless of the
diagnostic runtime result.

## Bite 3 source-containment and restart-domain definition — 2026-09-22

Planning-only contract update in `contracts/stop-then-resume.md`. The selected
candidate binds operation and source-invocation IDs, owner/lineage generations,
source session, runner incarnation, daemon incarnation, sealed roster, and the
original owned POSIX PGID. SID corroborates launch identity but does not widen
PGID authority. Membership/escape coverage must span launch through exclusion,
including reparented writers and PGID/`setsid` changes after admission fencing.
The current lane-owning daemon must durably fence every source creation,
recovery, adapter replacement and takeover path before interrupt/shutdown;
monotonic source-exclusion observations join that fence to a supported OS-domain
witness. Missing coverage refuses before stop; lost or conflicting evidence
after stop may have been dispatched leaves the operation indeterminate, retains
claims, and creates no target.

Static boundary inspection found no authoritative producer for this contract:
`popen_runner` establishes a new session, `_process_evidence` reports only the
runner PID/PGID, and `_RunnerConnection.close` signals the original PGID and
checks its liveness without proving complete membership or escape coverage.
The daemon identity does not prove that every fresh-adapter or external
recreation path consumes a durable restart fence. The loopback probe is also
not a positive witness: source, target, and observer share one container;
history is temporary; cleanup removes that container; and `validate_isolation`
does not check `HostConfig.RestartPolicy`. Current production disposition is
therefore **unsupported preflight refusal**. No test or runtime experiment was
run for this planning update. A source-only harness requires a separate scoped
design, and the existing loopback report keeps `support_claim: false`.

## September 22 approved stop-then-resume tranche

The [v1 decision](../../openspec/changes/separate-swap-ctx-handoff/stop-then-resume-decision.md)
supersedes the earlier keep-all-target-guarantees direction only for a new
explicit mode. No target process is created before release; preparation is
`ready-to-resume`, not restored-and-held. Strict mode and existing records
retain their evidence gates. Source containment, history, claims and unknown
effects remain safety requirements in both modes.

Implementation begins with a distinct isolated runtime fixture under T003/T004.
The independent native unenroll correction under T014/T024 was inspected but
deferred to keep the first v1 experiment on the critical path. Existing
focused results below remain a baseline, not results of these new changes.
Broad release tests, real accounts, production activation and installation
remain unverified; no checkbox is closed by this governance amendment.

### V1 test-first baseline

Sol ran the frozen probe-only diagnostic through
`tests/run.sh --parallel-safe -k test_lane_managed_loopback_probe` with private
JUnit output. Result: **61 passed, 2 failed, 2,172 deselected, 5.92 seconds**.
Both new tests failed on the expected missing `StopThenResumeV1Ledger` in the
unchanged harness. This is red-phase evidence, not acceptance or a runtime run.
Pre/post source and mode manifests matched. Private artifact basename:
`openrepotools-sol-v1-probe-red.Yidz4g` in the bench temporary directory.
JUnit SHA-256:
`cf7434f101215c406395e060c709b4ea87e2d077bc01147253f420508b73be79`.

An intermediate frozen diagnostic selected both loopback and Gate 0 probe tests:
**99 passed, 2,140 deselected, 7.27 seconds**. Pre/post content and mode manifests
matched; private artifact basename `openrepotools-sol-v1-probe-mid.clZCSn`.
JUnit SHA-256:
`a9175556c4c1550551d09190a7d4b51e16773231468cf165b4e0f77d3930d7bb`.
This precedes fixes for unknown process observations, source parser uncertainty,
negative-arm baseline validity and directory-sync failure. It is not the final
candidate or runtime evidence.

### Frozen v1 candidate and bounded runtime results

Final focused diagnostic:
`tests/run.sh --parallel-safe -k 'test_lane_managed_loopback_probe or test_lane_managed_probe'`
with private JUnit output: **113 passed, 2,140 deselected, 5.57 seconds**.
Content and mode manifests matched before/after. This includes the source
truncation/read-failure gate correction after the 112-pass pre-correction
snapshot; only the final hashes below identify the runtime-tested candidate.

- Probe SHA-256: `a77f6df765e032fcc815942d6c9ba28af09d4888ca01527fde2827f999cb077b`.
- Test SHA-256: `b6aa64f7395948b0eb32ce311e0d33a14672029c1418a55659c96d3cadf22e49`.
- JUnit SHA-256: `bad514dee853f9e1226b94dd9e467b125951daacaee1d2bcde9bb9d5f66d76c9`.

The [three isolated runtime arms](live-validation.md) demonstrate persisted
release-before-target ordering, saved-edit preservation, an otherwise-valid
unknown-effect refusal and no target without release. The release arm observed
the same parent session UUID, but a startup task event caused the history query
to be skipped; restoration remains **inconclusive**. Native child/tool/sleeper
stop observations are separate from harness-enforced parent termination.
Complete source containment, parent/child history restoration and actual
accounts remain unverified. The public v1 lifecycle is not implemented or
enabled. This completes a bounded T003/T004 investigation slice only, not those
whole tasks or T027–T032 acceptance. Native unenroll and the historical broad
regression failures remain open; the full serialized/platform/legacy gates
were not rerun. The preexisting bootstrap directories remain untouched.
Final strict OpenSpec validation and `git diff --check` passed. Probe/test
hashes remained unchanged. The original evidence manifest was verified after
copying the private artifacts to durable state; see `live-validation.md`.

### Startup-event/history follow-up: test-first baseline

Checkpoint `6c3cbfa` was committed and pushed before this follow-up began.
Sol froze the five new diagnostic tests and ran
`tests/run.sh --parallel-safe -k 'native_task_evidence or history_integrity'`:
**5 failed, 2,253 deselected**. Two failures were the absent lifecycle-sanitizer
helper; three were the absent history-integrity helper. This is the expected
red phase, not runtime or release evidence. Source and mode manifests matched
before/after; the probe retained the previous candidate hash.

Private artifact basename: `openrepotools-sol-t003-t004-red.8NeqDc`.
Test SHA-256: `d338c5b9b0338f680ec3f6a393c78dae3f336503f760dfc6f22f1bd9ece99f63`.
JUnit SHA-256: `3eab6adad45f55750e5939c6246199547f4f75b3f56873b2d5a5722827a06f0e`.
The first frozen implementation passed **124 tests, 2,140 deselected** across
both probe modules, but static review rejected it for unwired runtime history
discovery, unbounded/racy file reads, overly broad identity extraction,
correlation against preceding target rather than source events, and a history
snapshot taken after the optional query. Passing helper tests did not establish
the actual observation path. No runtime experiment used that candidate.

Superseded candidate probe SHA-256:
`98776f4a4f5fb7467b1ef23f34eef9a5d2c6780a3d2397f8e4e61ea7b80a9b7f`;
test SHA-256: `6a11737e3352aa886b95427853e8ae22b4a48e7d4d477c39125e138bd0c28ce7`.
Private artifact basename: `openrepotools-sol-t003-t004-green.sVG97I`.
JUnit SHA-256: `16b8eae7dd0cf5e8a0e2214db5ecba59fa556897bce8e91c7d6bf5d6e6021d1d`.
Source and mode manifests matched before/after.

The next frozen candidate reported **131 passed, 1 failed, 2,140 deselected**.
The failing directory-entry-limit fixture expected `scan-overflow` but observed
`missing-parent`; source and mode manifests again matched. Static review also
required an immutable source-terminal correlation reference and separate source
event completeness from target replay classification. No runtime probe used
this intermediate candidate either.

Intermediate probe SHA-256:
`a3851a4ba3383559ee2dea46cf166b131dbe0492640b340bbad6fbc77fbcbda1`;
test SHA-256: `f923c77aa470bf9a243e253ff34b725063fe324f34bcbedeb660a3274b71f015`.
Private artifact basename: `openrepotools-sol-t003-t004-corrected.G6LyTf`.
JUnit SHA-256: `81feec8846acc887b76202835b2c9874eb12b0fc1d4c8fba67792f6f0de0894d`.
A subsequent frozen diagnostic passed **134 tests, 2,140 deselected** in
12.97 seconds, with identical pre/post content and mode manifests. Review
confirmed the path, seed and snapshot corrections but required one final
sidecar-attribution fix: absent expected linkage must not promote candidate
child bytes to observed. This candidate was not runtime-tested.

Intermediate probe SHA-256:
`2ada9b98f433d40a8897c9b0389f818dfe3ee6a020b79767cf88fc0199313699`;
test SHA-256: `9e0a3051f48249eb6db710348a3b68f924604d5b3f7fa99303a8b45943477924`.
Private artifact basename: `openrepotools-sol-t003-t004-final.jQVIcq`.
JUnit SHA-256: `15dd3ab76f558751e862ce30f45e973cd358a3838872880cc3ddd90d1b9dbe69`.
### Final startup-event/history diagnostic

The final sidecar-attribution correction passed **137 tests, 2,140 deselected**
in 12.35 seconds through the same frozen two-module diagnostic selector.
Content and mode manifests matched before/after. Root inspected the final
linkage correction following Astra's qualified approval for isolated execution;
OpenSpec strict validation and `git diff --check` passed.

- Probe SHA-256: `6d934b044939c9a01c54f333a4c9c2b77a1219fad55adf312d1ac7426fa1d53d`.
- Test SHA-256: `ad86a7090baeea1280c212959b0fba9eae51bdfa26f397ea2c5c72a4da5df9b7`.
- JUnit SHA-256: `a46dd0b760b52ced86375736fab98a0a92b5e08a410584baef7ff6a28beeb42f`.

Sol then ran one explicit-release arm against the unchanged runtime/image pins
and isolation. The startup event was `task_notification/stopped`, matching the
source terminal's session/task digests. Its tool-use ID was absent while the
source supplied one; agent identity was absent and the event UUID differed.
The immutable source seed was observation 4. These facts remain
`live-or-unresolved`, not exact replay or child recovery. UUID difference alone
is not the unresolved-join reason. The extra history query remained blocked.

The measured parent and candidate-child original byte prefixes survived both
stop and startup. The candidate child is still unattributed, and stored bytes
do not prove runtime loading. Parent termination remained harness-enforced;
complete source containment and actual accounts remain unverified. Detailed
sizes, boundaries and report hashes are in [live-validation.md](live-validation.md).

Durable private artifact basename: `openrepotools-sol-t003-t004-sidecar.e63Nfv`.
Artifact manifest SHA-256:
`f616066d799bd6da4dfec016c3a3e057eea9096ee1d6a06de8bf4ed11352360e`.
The copy was manifest-verified, with directories `0700` and files `0600`.
This completes the bounded diagnostic follow-up, not whole T003/T004 or release
acceptance. The full serialized/platform/legacy suites were not rerun, public
v1 remains unimplemented, and no installation or production activation occurred.

### Deferred native unenroll correction (static review)

Astra identified three native/legacy mismatches to cover in T014/T024: the
legacy claim helper omits native lineage/child-worktree claims; recovery's
legacy claim-index matcher can mistake native claims for absent ones; and
removing the coordinator while retaining live native context can fail reload
with `native context coordinator changed`. The last is a concrete candidate
for the recorded CLI failure, not a freshly reproduced diagnosis.

The bounded repair needs exact claim snapshots and stop/effect proof before
any release, durable child-worktree-before-lineage progress, preserved source
history before workspace authority is removed, and atomic retirement of live
native records before coordinator removal. Native state release APIs are not
idempotent; recovery must reconcile the exact persisted intent and index,
not catch-and-ignore a second release. Final daemon cleanup must preserve or
restore the exact discovery endpoint if the same owner remains after a failed
clear; read back mutation-succeeded/journal-failed cases before restoration.
Never recreate a cleared owner or overwrite a changed endpoint. These changes
and their crash-window tests are not yet implemented in this tranche.

## September 22 continuation baseline and release disposition

### Bounded routing and archive correction

Luna implemented immutable native-child caller/transport bindings, exact
retry-before-lookup behavior, reload validation, and refusal before unsupported
delivery. Partial or removed metadata, changed accepted-result snapshots,
double-stripped bindings, and rehashed identity/policy mismatches refuse.
After source archive commitment, historical swap validation uses that exact
archive's swap interrupt selection; live selection remains mandatory before
commitment and is still cleared on invocation rollover.

Astra approved the bounded static correction at controller SHA-256
`175bc190b483ecce67e1e65a01ba7190b4f36173166c0d3b4c12777e2b719272`.
The first frozen candidate diagnostic reported **100 passed, 3 failed, 2,129
deselected**, **89.95 seconds**. It includes the previous six modules, the new
native-child-routing module, and bounded generic submit/reload/recovery cases.
The native pump and original child-routing positive case passed. Failures were
the known native-unenroll ownership conflict and two new test-assertion defects:
checking a message ID among dictionary keys, and expecting live selection
clearing immediately at release rather than at the next invocation rollover.

JUnit SHA-256: `9d166ccb7f0664432d0614e87dc8aa0bbf71c6a9b66835e58bd1aace253bda23`.
Content/mode manifests were unchanged before/after, respectively
`26b0107daea7c28300686115d93d523d0ff57c5da4fdfba26d3812e138c8dedc` and
`e86386105b42d952b5125bf50d357f5bb19931e66d8c762ecacaa294fb89b307`.
Private evidence is in `py-bench` under
`${XDG_STATE_HOME:-$HOME/.local/state}/openRepoTools/takeovers/2026-09-21-swap-ctx-handoff/sol-routing-focused-100p3f.ARyzUK`.
An earlier positional-selector invocation unintentionally selected the whole
suite and was terminated; it supplies no acceptance result. The completed
diagnostic used the wrapper's bounded `-k` selector.

The corrected frozen rerun used the same selector and added a dedicated
post-cleanup archive reload case. Result: **103 passed, 1 failed, 2,129
deselected**, **104.08 seconds**. The sole failure is the known persistent CLI
native-unenroll `ownership-conflict`; routing, socket, pump, swap archive,
generic submit, reload, and selected recovery cases passed. The controller
digest above is unchanged; only the two corrected test files were overlaid.
JUnit SHA-256: `ce1762ec2fd0509a4723782f90b87ffeddf2f9a163ae5201869c257bd0fdfcb0`;
log: `9fb58852b5a682a0e0a09f0eaaa60e3c0aac2b9fa0a1e81e49e3fe351da96789`.
Content/mode manifests matched before/after:
`85e666bfd30d87a8c5d7675e1b58c9dfc8dac8084180e6eeb09f870ec6b21b47` and
`e86386105b42d952b5125bf50d357f5bb19931e66d8c762ecacaa294fb89b307`.
Durable evidence is `sol-routing-focused-103p1f.qjUYRg` beside the preceding
private evidence directory. These isolated diagnostics do not replace the
serialized full suite, legacy/platform gates, or authenticated runtime proof.
No task is newly closed and activation remains blocked.
Strict OpenSpec validation of `separate-swap-ctx-handoff` and `git diff --check`
both passed on the actual feature worktree after the correction.

### Starting baseline and preserved release decision

Speckit prerequisites resolve this existing feature and its tasks, plan,
research, contracts, and quickstart. The specification-quality checklist is
38/38. Release checklists remain open: compatibility 6/22, lifecycle 6/29,
ownership 6/24, security 6/25, and testing 6/27. The user explicitly requested
implementation of the known-incomplete completion plan; no checklist was
silently completed or used as runtime support evidence.

Sol's frozen six-module diagnostic ran in `py-bench` through
`tests/run.sh --parallel-safe`, selecting transport accept, native worker
boundaries, native swap pump, persistent CLI lifecycle, native swap integration,
and native swap fences. It reported **60 passed, 3 failed, 2,153 deselected**
in **79.84 seconds**. JUnit: `openrepotools-sol-six-module.ncwndk/six-module.xml`,
SHA-256 `617bd15fa98d6e6eedb678fd2223d6d331251fd312d819c5920eb98c13b4de29`.
Content/mode manifest SHA-256 values are
`0e4517cfd44619c8cefd1803eeeecdcc6947015de3a958e7c0698a0628a36621` and
`a158011ed589705b9f69ae535f9962305a7ac536902f9183a09d3a8bfc2622a0`;
pre/post source and mode manifests compare equal after excluding run outputs.
The pinned submodule was present at
`39d5c986fcfac1a160474bfe91c5f1c37fccc72c`.

The inherited historical-shutdown and transport corrections passed their
selected regressions. Three integration requirements still failed:

- Persistent executable CLI lifecycle reaches successful swap recovery,
  target release, and shutdown, then unenrollment refuses ownership conflict.
  Static review found participant-only claim cleanup omits native lineage
  claims; the state-store refusal is correct. Native claim release/recovery
  and daemon ownership finalization need coordinated implementation.
- The native pump sends B exactly once but cannot send C. One bounded
  diagnostic exposed `stale-generation`: native swap interrupt evidence is
  not joined to its selection. Diagnostic JUnit SHA-256:
  `34d646f360a3461a10e56f3457c44f77cc51085036a8451c275f40a225902335`.
  It reported one failed case and 2,215 deselected in 11.43 seconds.
- A joined native-child target is refused as an unenrolled participant at
  submit. Luna's T013/T018 routing correction is being reviewed and needs
  separate candidate evidence.

This is a focused baseline, not a new broad census or release gate. The user
subsequently chose to **keep the guarantees, prepare upstream runtime
requirements, and leave activation blocked until supported**. See the
[requirements packet](../../openspec/changes/separate-swap-ctx-handoff/runtime-support-requirements.md).
No authenticated probe, installation, merge, runtime support, or new task
closure is claimed by this result.

## 2026-09-21 worker/recovery implementation and runtime feasibility

The next authorized slice started at published checkpoint
`0d14ffb425fea4ce1a847fd545b9124aea0f441b`. Sol remained the sole diagnostic
executor; Luna implemented bounded fixture corrections and Astra reviewed
their authority boundaries. No production safety guard or positive requirement
was relaxed.

Command in `py-bench`: `tests/run.sh --parallel-safe -k
'test_lane_managed_native_worker_boundaries or test_lane_managed_native_swap_pump or test_lane_managed_cli_persistent_lifecycle'
--junitxml=<private-artifact>/worker-pump-followup.xml`.

The pre-edit frozen baseline reported **13 passed, 15 failed, 2,172 deselected**
in **45.58 seconds**; XML
`openrepotools-sol-worker-pump-baseline.AX3mDH/worker-pump-baseline.xml`, SHA-256
`9d3c35eab86233c902c80d11f1518563c5c191bd01dfb13ca2a86152ac08a2c9`.

The first corrected snapshot reported **25 passed, 4 failed, 2,172 deselected**
in **36.36 seconds**. Artifact
`openrepotools-sol-worker-pump-followup.DpEcfE/worker-pump-followup.xml`, SHA-256
`facd98b837dac83099321c7d93d17404932dde995d96e51e598ad981dcffca90`.
Source/mode manifest hashes are
`0793e133b810354071ee96934ed59918d50f681ed457b41c32e469bf3c857dba` and
`ea21b347a0c9618e8c9fe72963cd638da48452a90f05c9c03233e3e3fd8432ec`.
Pre/post source and modes compare equal in both runs. The extra case covers
an observation exactly at the child-start watermark as well as one before it.

The manual-ingestion fixture now supplies its missing immutable startup and
mailbox source join, explicitly labeled synthetic and checked by real reload
validation. A correlated TaskProgress advances the ledger beyond child start.
Wrong source identity and before/equal watermark rejection still assert no
durable mutation. The positive child-route case remains unchanged and fails
because native children are not yet resolved by `submit`; physical coordinator
queueing needs the full durable semantic-target binding contract, not a generic
parent-send fallback.

The CLI now distinguishes a refused new request ID from resuming the original
operation ID after a shutdown crash. Its first follow-up still timed out before
reaching those assertions. The pump follow-up exposed an incorrect rollover
expectation for B, the replacement runner's first invocation, and a remaining
socket failure. Later evidence must verify those corrections separately.

The subsequent five-module frozen diagnostic added
`test_lane_managed_native_swap_integration` and
`test_lane_managed_native_swap_fences` to that selector and reported
**44 passed, 4 failed, 2,153 deselected**, **123.81 seconds**. XML
`openrepotools-sol-five-module.d6EyPg/five-module.xml` has SHA-256
`52eb5209935ab311d6708f960e2fecd406e9ee072e7ca85fa2e05e962e684b52`.
Source/modes remained unchanged and strict OpenSpec validation passed. The
durable copy is `sol-five-module-evidence.8CYrkI` under the same private
takeover directory. This snapshot aligns the CLI fixture's server/subprocess
budgets to 10/15 seconds and corrects B to an initial target invocation and C
to the sole same-runner rollover; production deadlines are unchanged.

The CLI now passes same-ID recovery and target release, then refuses shutdown
with `stale-generation`. Both pump cases still fail with socket resets, without
a captured server exception. The unchanged positive native-route requirement
is the fourth failure. The worker-observation cases and existing swap/fence
modules pass in this snapshot. These deeper failures remain open, not waived
by the fixture corrections or by strict artifact validation.

Architecture tracing found a concrete shutdown conflict: shutdown completes
the prior swap, while native-swap validation rejected its preserved released
state under phase `complete`. Historical acceptance must retain the complete
six-stage evidence validation, release joins, and source archive rather than
erase the released state. The CLI fault injector also must not reinject the
source-shutdown fault during a later target shutdown.

The transport's repeated `wait_for(sock_accept(...))` cancellation is a
source-backed candidate for the unexplained resets: a timeout can discard an
accepted connection before the waiting server consumes it. A persistent accept
task with non-cancelling poll intervals needs deterministic boundary and
pending/completed cleanup coverage before this is claimed fixed.

### Bounded production corrections and regression baselines

The controller now permits completed historical released swaps while requiring
their unchanged full six-stage proof. Completed held swaps remain a distinct
case with no fabricated release proof. A source-only one-shot shutdown fault
keeps the CLI fixture's later target shutdown meaningful. New cases cover real
shutdown/reload, missing historical release evidence, altered source identity,
and held-target shutdown. The unchanged guards continue to validate all archive
and release-identity joins.

The listener now owns the accepted socket synchronously in a Unix readability
callback before signaling readiness. Non-cancelling polling preserves that
pending accept; stop/cancellation closes unconsumed sockets, removes its reader,
and retrieves errors. Sequential handling and operation deadlines are unchanged.
Twelve deterministic transport cases cover poll retention, single response,
pending/completed cleanup, cancellation before publication without yielding,
handler cancellation, retryable/fatal accept errors, and stale callbacks.
These prove ownership invariants, not reproduction of a kernel scheduling race.

The new history/CLI regression was run against the old controller/transport
with only the corrected test files overlaid on the prior frozen snapshot:
**3 failed, 2,200 deselected**, **38.73 seconds**, each reaching shutdown's
`stale-generation` refusal. Artifact
`openrepotools-sol-history-red.03KfOg/history-red.xml`, SHA-256
`67314cf27e25c5296981b8ef5d27f4a7c34f085cfada42a349c0637ae1aeb349`.

The baseline transport test instruments both old and new polling surfaces and
asserts cancellation at the poll boundary separately from shutdown cleanup.
Against the old transport it reported **1 failed, 2,215 deselected**, **10.99
seconds**, on `poll timeout cancelled the accept`, not a watchdog timeout.
Artifact: `openrepotools-sol-transport-red.EzgW0i/transport-red.xml`, SHA-256
`a3b6aa1df9b2ba500b583d353f598e938be92d90a2748239c1156b0278a38309`.

Astra reviewed both production boundaries and the final tests without a
blocking finding. Candidate results must still be reported separately; neither
baseline failure nor review constitutes a passing gate.

The pinned-runtime audit and one bounded no-auth positive-orphan probe are
recorded in `live-validation.md`. The probe is **inconclusive**, not production
support. Baseline, follow-up, and probe artifacts were copied without overwrite
to private durable bundle `sol-worker-pump-evidence.vq19mi` under the takeover
artifact directory; hashes, modes, and symlink targets were verified.

This is a focused diagnostic, not a new broad census or serialized release
gate. Native ctx/restoration and production evidence remain open; no task
checkbox, governance approval, authenticated canary, installation, or merge
is claimed.

## 2026-09-21 follow-up — owner-fence fixture repaired

The user authorized committing/pushing the takeover checkpoint and continuing
the next implementation step. Checkpoint
`5e940f00ec4b1d82dc9be0510b94b881316db631` was pushed and verified on
`origin/001-separate-swap-ctx-handoff`. The bounded T012 follow-up changes only
the native-swap fence test and checkpoint documents, not production behavior.

A diagnostic helper retained and re-raised the original takeover exception.
All five cases reproduced `fixture runtime identity is unavailable`: the
shared start/serve harness did not publish supervisor discovery, so recovery
was never reached. Diagnostic result: **5 failed, 2,195 deselected**, **20.76
seconds**; artifact `openrepotools-sol-fences-diag.wC5RED/fences-diagnostic.xml`,
SHA-256 `035205a174bec3243845bbff1bd4ab33d1b1b6997707fd2b2a209a1e43a48431`.

The fence-local setup now calls the real daemon `register_runtime` API after
socket readiness and asserts the published owner/generation/domain/process/
socket identity before arming the fault. Recovery, exact exclusion validation,
claims, all five boundary effect limits, and retry/no-replay assertions remain
unchanged. Astra's bounded review found no blocking issue. The injected
exclusion remains a simulated test fault, not proof of live supervisor death.

Command: `tests/run.sh --parallel-safe -k
'test_lane_managed_native_swap_fences or test_lane_managed_native_swap_integration'
--junitxml=<private-artifact>/fences-integration.xml` in `py-bench`.
Result: **19 passed, 0 failed/errors/skips, 2,181 deselected**, **63.79 seconds**.
Artifact: `openrepotools-sol-fences-final.swVB3F/fences-integration.xml`.
XML SHA-256: `5e40071b98941e09165c77fb6c63ee0ce0836d1a6e9a4d2d96cd776fea4e6465`.
Source/mode manifest SHA-256 values:
`149aaae83d567112d041c105090bce3e3dae22bcc42a65fa8943a64e4e92dda6` and
`69273419db6da571565b75a8514dc1ca42d42cb2dded187752af1ab1d0f4a720`.
The frozen source and modes compare equal before and after the run.

This closes the five reproduced fixture failures only, not T012 or a release
gate. The latest **broad** census is still the 34-failure snapshot below; do
not manufacture a new broad count by subtracting this focused result. Native
ctx/restoration, worker-observation integration, persistent recovery/pump, and
legacy/full serialized gates remain open. No authenticated probe or installed
cutover was performed.

## 2026-09-21 takeover — prior broad diagnostic checkpoint; 34 failures

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

## T046 source-to-target native task seed — offline PASS

The future-only implementation emits a bounded digest-only terminal task
seed from the source phase and binds it to the source parent and invocation.
The source-phase digest, release and target-launch intents, and target-spec
fingerprint all bind the same seed digest. Missing or incomplete
session/task/agent linkage is INCONCLUSIVE before release and target creation.
The target validates the complete fingerprint before any CLI subprocess and
uses the seed with the existing strict native-task correlation logic; the
sticky startup gate is unchanged.

Astra's architecture review passed. Sol ran the canonical
`tests/run.sh --parallel-safe -k two_domain --junitxml=<private-output>` in
`py-bench`: 155 selected, 0 failures, 0 errors, 0 skips, 5.715s. Frozen source
hashes: native probe
`1042153b8f768f1bce772bc42d3f923b3d05d7a3fb944070c5327b7b5624c77d`, harness
`b0f01d529771eab2d7ebd1738b8702e25bfc2b9fc446e7236548088cad63338e`, tests
`d4242957190624b76d652457bd9b0376e99d3d2985820666021845356b016c33`. Private
stdout SHA-256 `c814255cf7389dc648e5fd716f5b51ea3e3315f2fbbfe01a3e43f221a7bc47f1`,
stderr `86f6eb7619462ab78a90aa0abc9b742ff92b177ad917fcadb536263132880278`,
and JUnit `77c40a78dbb69b6e586e6f037f3906b2c61b1cc1a16e9ab77b2c666d1b4dc9c4`.
The ninth runtime attempt exercised the source-native-task-terminal-seed-
unavailable refusal. This did not exercise available-seed transfer, target
fingerprint validation/correlation/startup/history query, or the negative arm.
The eighth result remains historically INCONCLUSIVE, and Bite 5 remains
pending. At the T046 checkpoint, no tenth run was authorized.
