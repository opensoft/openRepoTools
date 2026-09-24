# Isolated Native-Worker Live Acceptance Plan

Status: **INCOMPLETE — LIVE UNVERIFIED**. The isolated initialization baseline
below ran without credentials or network access. Scripted gateway controls
below establish a bounded interrupt candidate. Authenticated acceptance is
**NOT RUN** and full Gate 0 acceptance remains incomplete.

Latest Bite 4 status: none of thirteen runs produced a PASS. The user
authorized exactly one thirteenth run, and Sol reviewed/froze the command. It
exited 2 after about 20 seconds, INCONCLUSIVE with positive reason
`effect-or-observer-uncertain`; the negative arm was not run. Source
stop/removal and target-state volume creation preceded source-report schema
validation failure, before copy, release, or target-container creation. Its
inner source exception was not retained. Zero labeled containers and two
unattached labeled volumes (one source-state, one target-state) remain
preserved. No replay of the thirteenth run or cleanup is authorized. The user
has since authorized exactly one fourteenth full diagnostic run, pending
push, Sol's post-push preflight/command review, and the required command seal;
do not start before all are complete. The authorization grants no cleanup or
deployment authority.
T050's future-only source-report correction has Astra architecture approval
and Sol's 427-pass canonical offline gate (2,168 deselected, zero failures).
The historical thirteenth result remains INCONCLUSIVE; Bite 5 is pending and
production remains unsupported.

## Thirteenth full Bite 4 runtime — INCONCLUSIVE

The public report records overall `INCONCLUSIVE`,
`bite5_decision=pending-review`, `production_disposition=unsupported`, and
`support_claim=false`. The positive arm is INCONCLUSIVE with
`effect-or-observer-uncertain`, `observer_complete=false`,
`cleanup_complete=false`, and `release_candidate_ready=false`. The negative
arm is `not-run` with `positive-release-candidate-not-established`,
`positive-cleanup-incomplete`, and `positive-observer-incomplete`; no target
container was created. `explicit_release_selected=true` records the selection
only; release did not occur.

The source container was observed running after the source phase, then stopped
and removed. The target-state volume was created before source-report schema
validation failed; copy, release, and target-container creation were not
reached. The sealed artifacts contain no inner source exception and no event
indices. The unbound legacy/source `parent_uuid` reference is a deterministic
static cause candidate, not a directly proven historical exception.
Quarantine counters are zero, `volumes_removed=false`, and
`leftovers.manual_review_required=true`. Two unattached labeled volumes remain
preserved, with zero labeled containers. No cleanup or retry is authorized.

Manifest SHA-256:
`5815a42167d5a772131368264111f9cb124f726fe33e101dee318eb3f8bd9d23`.
Sanitized stdout:
`cd94d74854d88431c178b17b8893179e34b8821034e4570f02986051a86f374a`.
Private report:
`55d8311397fa473ee85612ea0e95c60ce6aa0caee074d2f360632964b6ab146e`.
Abort ledger:
`b898eabb9f181fdcbf8a0c00d11f36090417d9ad62059bc8a183072d8ba557a8`.
Runtime pins: SDK 0.2.153, CLI 2.1.273 SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`, and
image SHA-256
`a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094`. At that
thirteenth-run checkpoint, no fourteenth attempt had been authorized. Bite 5
remains pending and production unsupported.

## Historical twelfth full Bite 4 runtime — INCONCLUSIVE

The twelfth invocation ran once under separate authorization and exited 2.
The public report records `diagnostic_status=INCONCLUSIVE`,
`bite5_decision=pending-review`, `production_disposition=unsupported`, and
`support_claim=false`. The positive arm reason is
`startup-task-event-observed`, with `observer_complete=true`,
`release_candidate_ready=true`, and `cleanup_complete=false`; the negative arm
is `not-run`.

Source stop event 34 and target stop event 151 were harness/engine enforced
with exit 137 and `oom=false`. Source removal was event 36, exact copy
verification event 92, pre-release custody event 119, durable release event
120, launch intent event 121, target creation event 123, target removal event
153, final helper removal event 179, and final-custody persistence event 180.
The target produced one complete stopped `system/task_notification` matching
session/task, with optional agent/tool identity unknown. The event UUID
differed from the source parent. The gate recorded
`successful_result_seen=true` but `history_query_allowed=false`, so neither
query nor read was sent. No parent/child startup messages were observed.

Final custody retained the saved edit and linked source-parent history prefix.
The target parent JSONL grew from 52,825 to 55,372 bytes and
`other_config_mutation_count=1`, so the run does not prove the entire target
tree stayed unchanged. The negative arm's generic reason
`positive-release-candidate-not-established` is misleading: release candidate
readiness was true and the unmet prerequisite was `cleanup_complete=false`
after preserving the INCONCLUSIVE run. The sealed result digest is
`4289f073b7c8508633f13c829d0ed670c813f917480ff106bd0525d14ee24294`; full
artifact hashes are in [`verification.md`](verification.md). No loaded-history
proof or Bite 3 OS witness/all-path restart fence exists. The 19-volume and
five-container inventory above describes the state before separate authorized
cleanup.

### Post-run authorized cleanup — complete

On 2026-09-24, after the sealed twelfth-run bundle was verified, Sol High
executed the exact authorized cleanup. Preflight found 19 labeled diagnostic
volumes and five stopped containers, with no running containers or unrelated
attachments. Postflight confirmed all 24 allowlisted resources absent. The
sealed evidence bundle and its 36-entry manifest are unchanged; no prune,
evidence deletion, or unrelated removal occurred. The private mode-0600
allowlist artifact SHA-256 is
`d6ea783b66a4bee326ee23b83d80a82797f2f633db19831b131b0ac4cd0a4d78`. This
post-run cleanup does not alter the INCONCLUSIVE runtime result or authorize a
thirteenth attempt.

## Historical eleventh full Bite 4 runtime — INCONCLUSIVE

The eleventh invocation exited 2. Its v3 source seed was available through the
SDK-sidecar proof, and the source projection marked the release candidate
ready. Source stop/removal was harness/engine enforced with exit 137, not
natural graph shutdown or production containment. Exact copy, pre-release
custody, and final custody were retained. Durable release event 120, launch
intent 121, and target create 123 were recorded; final custody is event 180.
The target harness stopped/removed with exit 137. Its one complete stopped
`task_notification` matched session/task; optional agent/tool identity was
unknown and its UUID differed. The sticky gate skipped the history query. No
parent/child startup messages were observed, and the negative arm did not run.

The sealed result digest is
`9403d9910279ec0c6f047f53dc4d1c672751e90bb63d637985803c8202f04e5f`. The
private evidence bundle label is
`openrepotools-bite4-eleventh-preflight.YKJSLl` (35 files mode 0600, 16
directories mode 0700). Input artifact SHA-256
`439d6f044995bc84d5f73ae905970e9f64fbaca4f81871698cf530f0ffd718b0`; stdout
`f47cb555d77747029072db22e63fba03d57b37e0d1e582d684057446d3ed6f04`; sanitized
report `0220f77e4d0f5a6b98e0e06f5f2bbc1bf23117c548215eac0637ecc43fcb1e21`;
arm result `5b19526a07fc5100e0cb33dec785fe14191c3de601e41d66ab4be09936da6320`;
stderr was empty with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The inventory is 17 volumes (11 source-state, six target-state), five older
stopped containers, zero running, and zero current target containers. No
cleanup, retry, or twelfth attempt occurred or is authorized. The result is
INCONCLUSIVE under Bite 3 and is not a Bite 5 verdict. Astra's post-run
assessment is that the sticky gate behaved correctly; no replay or loaded-
history proof exists. Next is read-only protocol investigation and separate
governance if progression criteria are proposed for change.

## Historical tenth full Bite 4 runtime — INCONCLUSIVE

## Tenth full Bite 4 runtime — INCONCLUSIVE

The tenth invocation exited 2. Four lifecycle-v2 events were complete: one
started task with a tool-use ID; one hook callback was rejected as
`hook-tool-use-id-mismatch`; zero callbacks were stored or joined. Event 146
persists the final result with sealed digest
`addefcf9282109879c5fd1eaa74a199eb03949e8b81ed8c13b4728a837db8258`. Full
artifact hashes and the preserved-resource inventory are in `verification.md`.

Astra's post-run conclusion is that rejecting the mismatched callback was
correctly fail-closed. The pinned SDK only forwards an optional callback tool
ID; it does not guarantee equality semantics with the selected task tool ID.
The retained summary omits rejected-hook event kind/digests, so the mismatch
cannot be attributed to a different tool role, task, or association. This is
not evidence of a CLI defect. A future investigation should retain bounded
rejected-hook event kind/order and separate callback/input/current-task/session/
tool digests, then seek an authoritative structured bridge. Do not relax exact
equality or infer from cardinality. The tenth authorization is consumed; no
cleanup or eleventh attempt is authorized.

## Historical ninth full Bite 4 runtime — INCONCLUSIVE

The one authorized ninth attempt ran once and exited 2. The sanitized public
report has `support_claim=false`; the positive arm is INCONCLUSIVE with reason
`source-native-task-terminal-seed-unavailable`,
`observer_complete=true`, `release_candidate_ready=false`, and
`cleanup_complete=false`. The negative arm was not run, and no positive
release candidate was established.

The source parent exited and tracked fixtures were excluded. Source stop and
removal were observed, followed by exact copy, identity-linked pre-release
parent-history custody, and final custody of the copied volumes. Source
container shutdown was harness/engine enforced with exit 137; this does not
show natural graph shutdown or production containment. The source projection
reports the seed unavailable but has no detailed unavailable-reason envelope,
so the exact missing identity/event condition remains unknown. The target-state
volume was copied, but no release or target-launch ledger and no target runtime
container were created.

The event ledger contains entries 1–145. Public event 146 is
`final-custody-result-persisted` and carries sealed arm-result digest
`982c9efb8b22b97d78e5eac557834523bb542edf7bc6dec5928bed93445a7aeb`, distinct
from the pre-release custody digest. T046's available-seed transfer, target
fingerprint validation/correlation/startup/history query, and the negative arm
remain unexercised. Its focused offline closure remains unchanged. The run
added two preserved volumes, bringing inventory to 13 total (nine source-state
and four target-state), five older stopped containers (four Bite 4 and one
metadata diagnostic), zero running, and no ninth-run container. No cleanup or
retry occurred. The one-run authorization is consumed; no tenth run or cleanup
is authorized. Full artifact hashes are in `verification.md`; raw paths and
runtime IDs remain restricted.

## Historical eighth full Bite 4 runtime — INCONCLUSIVE

Sol executed the separately authorized eighth command once. The outer process
exited 2 and the sanitized public report is INCONCLUSIVE. The positive arm is
INCONCLUSIVE with `startup-task-event-observed`,
`observer_complete=true`, `release_candidate_ready=true`, and
`cleanup_complete=false`; the negative arm did not run.

Source stop/exclusion, exact copy, pre-release identity-linked history
custody, durable release, exact-parent target initialization/start/stop/
removal, and final saved-edit/history custody were observed. The target
startup snapshot recorded one `system/task_notification`, status `stopped`,
provenance `target-observed`, sequence 1, and matching session correlation.
Task and agent were unknown, source terminal seed was unavailable, and
identity was unresolved; the snapshot is unknown/incomplete. No
assistant/tool activity, parent/child messages, or gateway routes were
observed. The sticky history-query gate correctly skipped the query because a
startup task event had been observed. This does not establish Bite 3 PASS or
decide Bite 5.

The run added two preserved volumes, leaving eleven total (eight source-state
and three target-state), four older stopped Bite 4 containers and one stopped
metadata diagnostic container, zero running, and no eighth-run containers.
There was no cleanup or retry. The authorization is consumed; no ninth run or
cleanup is authorized. Frozen code hashes and private artifacts are recorded
in `verification.md`; raw paths and runtime IDs remain private. Artifact
SHA-256: manifest
`3626f45bdea3b9932b5debbf7e946df7ad7ed5a47a83f552caf47334ba88ddd4`, report
`eba9d0dc0646697af4f453d6881d95d3055d97935a8d53b070ea034cfaee5383`, stdout
`ae51147de5c27869769f49a9e715864f9f3cff3d2be78fff9b36e2d938cfaba3`, arm
result `641242a7fe2625e0b978463d7a3c7aabab4bf3b053378d665e564ae89929be32`,
release `fcc6faabe0b0446dcf5cef5d763b17b9587c13e74798ed90eaeebd5709246e6c`,
and target-launch `808af1888b195193807600ad8192c43123888da1d7f1f79a1904e4fc475dfe60`.

## 2026-09-22 Bite 4 two-domain harness invocation — INCONCLUSIVE before source

Sol executed the corrected outer harness command once. It exited with status 2
after about 10 seconds and wrote a sanitized report with
`diagnostic_status: INCONCLUSIVE`, `support_claim: false`, and
`production_disposition: unsupported`. The positive arm was
`inconclusive` with reason `effect-or-observer-uncertain`; its abort ledger
states that the external Docker volume-create event was not observed. Inventory
confirmed one run-labelled `source-state` volume existed and it was preserved
for manual review. The missing event does not establish that Docker omitted
the create operation.

No Bite 4 selected-runtime experiment occurred: the source container and SDK
runtime were never started. No source history was produced, no release was
persisted, no target was created or started, and no startup or history-loading
observation took place. The negative arm was `not-run` with
`positive-release-candidate-not-established`. The post-run inventory contained
zero run-labelled containers and the one preserved source-state volume.
Quarantine removed zero resources; cleanup and observer completion were both
false. Keep the preserved source-state volume for manual review; no cleanup is
authorized.

This `INCONCLUSIVE` diagnostic report is not a Bite 5 verdict. Bite 5 remains
pending; no PASS/FAIL/INCONCLUSIVE decision has been made. Read-only diagnosis
of the missing external volume-create event is complete. It found exactly one
volume-create event in the engine's 120-second history window; its actor ID matched the
preserved volume. The event attributes contained only the volume driver and
omitted the custom run/role labels. A label-filtered volume-event query for the
run returned zero events, while bounded current inspection showed the expected
labels on the volume. This is a high-confidence observer/filter mismatch: the
label-filtered observer cannot receive the create event on this engine. It is
not evidence that the engine failed to create the volume.

At the time of this first report, no second experiment was authorized. Astra's
targeted architecture review of the future-only observer correction passed,
and Sol's offline gate passed as recorded below. The correction did not run in
this original runtime invocation; it has not been runtime-verified. A later
user authorization for one separate follow-up is recorded below; it does not
authorize cleanup of the old volume or any further attempt.

The run used SDK `0.2.153`, CLI `2.1.273` (SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`), and
local image `py-bench:brett` (immutable ID
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`).
Hashes from the original runtime attempt (before the future-only observer
correction) are respectively
`e092869a765cee41987f4be0d1019ab8223f1ede37814d52c543709d78bf3354`,
`4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695`, and
`33349e8a3349fff06a51816ea938cc5305996baacfc407ec7713dfcd464e9c28`.
Private artifact paths and raw runtime IDs remain in Sol's private execution
record. Artifact SHA-256 values:

- stdout: `b221ce74d8c899cb4b7f6c5d37cafbb85bdd77c6e2478273975197f94ecafdba`
- stderr (empty): `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- sanitized report: `398b1f5252ddac1b75434bac4eddb969ba95bb7b1f4d6b1a822c1f0b0d6319ac`
- arm abort ledger: `37a81957dc574b3118c8af254f637c405b3ea3428779f569fb130190953af356`
- quarantine summary: `7cf190500e945ff7e1d15afdd69bbab5a4805244b065675473a07079e9d5b51a`

## T033 future-only observer correction — offline verified, not runtime verified

Astra's targeted architecture review passed the future-only event-observer
correction. The parser now requires a nonempty `Actor.ID`, rejects a present
top-level `id` that is invalid or differs, and never treats `Attributes.name`
as a missing actor identity. Before the pre-release inventory snapshot, the
observer waits at most 10 seconds for the preregistered per-volume mount and
unmount counts while checking the independent container and volume streams for
health on each wake. Sol ran `tests/run.sh --parallel-safe -k two_domain`:
**39 passed, 2,293 deselected in 9.47s**. JUnit SHA-256
`91b1b34dc62cf8e34035eea99b6bbdb37b3675518f1585fa469f220be580c6ba`; log
SHA-256 `b62a03373d1fd2950579083ab6275d8b720143e8b7d5f4f9495fa5dcd1ec467e`.

Frozen offline hashes: harness
`1aa5f6f35beea569aa6c4f206cb7dcd08f9ee9d4cdea1bee5bc268ef34cd06b6`, helper
`4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695`, and
tests `5f5869655cc046674dbd697e3f816fd28ea66e38c0f4a0203225d1695d5e2bca`.
This selector is offline-only; it did not call Docker or the SDK. During T033,
no runtime attempt, volume inspection, or cleanup occurred. The preserved
source-state volume remains untouched. Bite 4 remains **NOT COMPLETED**, the
original diagnostic remains INCONCLUSIVE before source startup, and Bite 5 is
pending.

## Newly authorized Bite 4 follow-up — INCONCLUSIVE at source-container create

The user later authorized one distinct bounded Bite 4 run using the corrected
volume observer. Sol's fresh read-only preflight passed for SDK `0.2.153`, CLI
`2.1.273` (SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`), and
local image ID
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`.
Astra's read-only assessment found no concrete blocker to this separate run:
the first attempt had not stopped or launched a source, and its preserved
volume had no attached containers. It remained untouched and outside the fresh
run identities.

The corrected volume observer progressed past the source-state volume create,
but Docker's source-container `create` failed with exit status 125. The exact
daemon error text was not retained, so the cause is unconfirmed. Sol's
read-only diagnosis identified a moderate-to-high-confidence candidate defect:
the generated writable `--mount type=volume` argument includes an explicit
`rw` token, which the Docker volume-mount syntax may reject. Treat this as an
inference, not an observed daemon diagnosis; Astra agrees that any correction
must be future-only and offline-verified before another runtime can be
considered.

The harness exited 2 with `diagnostic_status: INCONCLUSIVE`,
`support_claim: false`, and `production_disposition: unsupported`. The positive
arm was INCONCLUSIVE with `release_candidate_ready=false`,
`observer_complete=false`, and `cleanup_complete=false`. The negative arm was
NOT RUN. No source container started, so there was no source SDK/runtime,
history, release, target, or startup observation. There were zero run-labelled
containers. Two `source-state` volumes are preserved (the original volume and
the one created during this follow-up); neither was cleaned or reused. No
cleanup, retry, or further runtime attempt is authorized by the one-run grant.

The outer `stderr.log` is empty (SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`), but it
does not contain the Docker daemon's exact create error. Private paths and raw
IDs remain in Sol's restricted record. The frozen harness/helper/test hashes
were unchanged: `1aa5f6f35beea569aa6c4f206cb7dcd08f9ee9d4cdea1bee5bc268ef34cd06b6`,
`4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695`, and
`5f5869655cc046674dbd697e3f816fd28ea66e38c0f4a0203225d1695d5e2bca`.
Artifact SHA-256 values:

- stdout: `794f6e7e954cf5bd2a39da185878ab6c42754e18c64c0f3cc6d91e01ded7350f`
- sanitized report: `08ab7467fe46d4ef1bf3a53216ff67b86fcdb8e3ed40913ccc03aba0ef273a96`
- arm abort ledger: `9dff73fb5cd0b7f2adf9d6a3e089359efa74d64709233a26ead37fc5998defb7`
- quarantine summary: `b6cd550366b186fd3166561ef3b00875d664efc555ba152705ff6414dbea6e3e`

This is the second distinct pre-source INCONCLUSIVE Bite 4 result, not a Bite 5
verdict. No PASS/FAIL/INCONCLUSIVE Bite 5 decision has been made. Astra passed
the future-only command-builder/private-error-capture review, and Sol's
tests/run.sh --parallel-safe -k two_domain gate passed 41 tests, 2,293
deselected in 9.09s. JUnit SHA-256 is
edb34b8404e20b3e8815e1b17a9b12f2b4347bfc1a75c6b1cebb0183cf552963; log
SHA-256 is 9376fd78c8c29678af02aefaa57c38d73bbefc7d0cf4bf0290fbe2d82e72b1f0.
A first gate had 40 passes and one test assertion failure; after correcting
that redundant assertion, the frozen 41-test rerun passed. Candidate hashes
and Astra's limits are in verification.md: retained stderr is capped at 4,096
bytes, but subprocess capture is unbounded, and timeout/pre-arm failures do not
use the ledger capture path. This offline correction does not confirm the
cause of the prior exit 125 or verify the full two-domain runtime. No further
full source/target attempt is authorized without new user authorization after
evidence review.
Production remains unsupported because the Bite 3 continuous containment
producer and all-path restart fence are absent.
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
retained. It is not a Bite 4 source/target experiment and does not change the then-current
Bite 4 INCONCLUSIVE results or the pending Bite 5 decision. At that smoke
checkpoint no third attempt had yet been authorized; the later one-run grant
and result are recorded in the following section. No cleanup or Bite 5 verdict
is authorized.

Private evidence SHA-256 values: commands
f6136e05ab0e834d41682e655c41c79f005d88786aaae5347f7806819badd517; inspect
5cad66170547b9a015dbbf2abd2791210f7bcb2b8718e6fe3f384deb3de7be0d; cleanup
3f15320367ab36900f00fe8e3ac19e292ab96081018b70556265077c90ba50d3. Raw
container/volume IDs and private paths remain in Sol's restricted record.

## Third full Bite 4 runtime — INCONCLUSIVE before source startup

After the separate T034 Docker-create smoke, the user explicitly authorized
one third full Bite 4 attempt. Astra's read-only pre-run assessment and Sol's
fresh preflight passed. Sol used the frozen T034 runtime candidate: harness
SHA-256 c5c183cb215ecf56f3ff028dd2e4175364a1d7f2720df6fcff29e9baadc7cdac,
helper 4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695,
and tests 3f7c5f63af5331d7bdc4116b04535bc6f549bb852b05a68cef318b115ab9e1ac.
The run exited 2 with diagnostic_status INCONCLUSIVE and support_claim=false.

The source container was created but never started. Independent inspection
reported state Created, Running=false, Pid=0, and Docker's exact unset-time
sentinel `0001-01-01T00:00:00Z` for both start and finish. HostConfig.Tmpfs
contained exactly /tmp and /opt/loopback, while
Mounts contained only the writable /opt/state engine-managed volume. The
validator incorrectly required configured tmpfs destinations to appear as
active Mounts entries and reported two-domain tmpfs destination mismatch.
No source SDK process, history, release, target, or startup observation
occurred. The positive arm reason was effect-or-observer-uncertain; the
negative arm was NOT RUN.

Quarantine also expected a die event for this never-started Created container
and reported quarantine-die-event-unconfirmed. It preserved the container
and its source-state volume. No cleanup or retry occurred. Engine inventory
now contains three labelled source-state volumes and one run-labelled
never-started Created container. The two earlier volumes remain untouched.
This result is Bite 4 INCONCLUSIVE, not a Bite 5 verdict; no fourth full
attempt is authorized. Production remains unsupported.

Private artifact SHA-256 values: abort ledger
ff62f4fa6026ef1bf3af4cf5af5b5bcacb322e809ce7c198265770e25ce50388;
quarantine summary
8c55e5d370934f22c612fb5e0cb126a023979349f131fcce551c3173c6c1848e;
sanitized report
e95ab2c945d6048cc454b32f0d949d8d65082ea65cf633c321e311289d6419cc;
stdout
34eea213ed27b67ee5ecf99a7dc1162e6fa6e35b2308a66265a8f6417c2a022d;
stderr (empty)
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.
Raw IDs and machine paths remain in the restricted execution record.

## T035 future-only correction — offline PASS; no runtime validation

Astra's targeted architecture review passed. Sol ran the canonical
`tests/run.sh --parallel-safe -k two_domain` selector in `py-bench`:
**59 passed, 2,293 deselected in 6.74s**. The strict predicate requires both
Docker timestamps to equal `0001-01-01T00:00:00Z`; missing, null, empty, or
malformed times remain uncertain. Pre-start tmpfs acceptance is limited to the
exact configured profile with only expected engine-volume mounts; immediately
after start, actual tmpfs mounts must validate before any SDK/helper exec.
Quarantine preserves a corroborated never-started Created container and
refuses uncertain start history.

This was a focused offline gate, not a runtime experiment. At that checkpoint,
the third full Bite 4 run was INCONCLUSIVE with three labelled source-state
volumes and one never-started Created source container preserved. A later
separately authorized fourth attempt is recorded below. Exact code/test and
private gate artifact hashes are in `verification.md`.

## Fourth full Bite 4 runtime — INCONCLUSIVE before any container exec

Sol executed the one separately authorized fourth attempt using the frozen
T035 harness/helper/test hashes recorded in `verification.md`, pinned SDK
0.2.153 / CLI 2.1.273, and immutable local image. It exited 2 with
`INCONCLUSIVE`. The source container started, but the first post-start
`validate_two_domain_isolation` call in `_install_observer_files` rejected the
inspect `Mounts` inventory because active `/tmp` and `/opt/loopback` tmpfs
entries were missing. `HostConfig.Tmpfs` listed exactly `/tmp` and
`/opt/loopback`. The validator failed closed before any container `exec`, CLI
or probe copy, SDK/runtime, history, release, target, or negative arm.

The positive arm is `effect-or-observer-uncertain`, with
`release_candidate_ready=false`, `cleanup_complete=false`,
`observer_complete=false`, and quarantine reason
`quarantine-container-preserved-for-custody-review`. Quarantine stopped the
new source container and preserved it Exited 137 with its attached new
`source-state` volume. The three older volumes and old Created container were
untouched: first two volumes unattached, third volume still RW-referenced by
that Created container. Current engine inventory is four `source-state`
volumes and two source containers (one Created, one Exited 137), with zero
running containers. Nothing was removed; no cleanup or retry occurred. The
fourth authorization is consumed; no fifth attempt is authorized. Bite 4 is
INCONCLUSIVE, Bite 5 remains pending, and production remains unsupported.

Astra confirms the fail-closed result is correct. Missing active Mounts
evidence is not proof tmpfs is absent. Any future evidence producer must use
exact-container mountinfo or a reviewed trusted pre-SDK attestation; do not
silently relax validation.

Private SHA-256 values: stdout
`2b09daf7efac84ba5386ab5578cfe14da3ec76bc1ddc415fc4d9835180dffc4c`, empty
stderr `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
abort `7a1c95d9bfb92cd3cf427f495626c6d39cd7e0a60043b3742db7c8a93e07ca8b`,
quarantine `f44acfbe54965a6bc8a2f15ee186122ceced3a19c7286d014e11f6e0c505338a`,
stop `635884ddb9445b6bc297e9ba1967b75b3097f9fafecf0be5a7fbc96ffb5ab79a`,
manifest `8bd8faa64245210d6c8a7cd2ac801e0798a300852f87a51f25aa640fd931cb80`,
and report `45a92030725db92a51c3f84b92ebd97561b8b7e2b40d8117f1162ca92a7c82f0`.
Raw paths and IDs remain private.

## Fifth full Bite 4 runtime — INCONCLUSIVE before source start

Sol executed the one separately authorized fifth run with the frozen T036
candidate, pinned SDK 0.2.153 / CLI 2.1.273, and local image ID recorded in
`verification.md`. It exited 2 with `diagnostic_status: INCONCLUSIVE`,
`support_claim: false`, and `production_disposition: unsupported`. The positive
arm was INCONCLUSIVE with `effect-or-observer-uncertain` and
`quarantine-created-never-started-preserved`; `release_candidate_ready`,
`cleanup_complete`, and `observer_complete` were false. Quarantine discovered
and preserved one never-started container, stopped/removed zero containers,
and removed zero volumes. The negative arm was not run because
`positive-release-candidate-not-established`.

Independent inspect confirmed the exact image ID, Entrypoint, full Cmd and
wrapper digest, `OpenStdin=true`, `AttachStdin=true`, and `Tty=false`. Docker
also reported `StdinOnce=true`, while the frozen host validator required
false. This is the observed reason for refusing before source start, not an
image-ID mismatch. No wrapper attach, SDK, history, custody, release, or target
ran. No Bite 4 source experiment progressed to its runtime phases.

The new source container and its RW-attached source-state volume remain
preserved. The previous four volumes and two containers were unchanged. Total
inventory is five labelled source-state volumes and three stopped source
containers (two Created, one Exited 137); none are running. No retry or cleanup
occurred. The one sixth full attempt is user-authorized after T038 review,
offline verification, and a fresh preflight. Its command and successful shell
review are in `runbook.md`; it has not started and awaits root GO. Bite 5
remains pending and production unsupported.

Private SHA-256 values: report
`891ae8b9c63a12655ea1b75b8179b024a1dc527111f33476ac659c512ebab731`, stdout
`94aae106ea4c43b392f482c31d2f8a221134f5590df07937cee1d85ee6361d25`, empty
stderr `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
arm-abort `cbbc3da6fbcfb029c02c48c035cb1f075b179fc191bc28221a1a165bb9d5112f`,
quarantine summary `f8938b474684fb1d79c32c92b87ac26d008f1534d61df4d1ba1757570092e209`,
and run manifest `64eda612e32e0f8d2ba72c640b385f4d30a88c4ceb55812e6b3c6e11c74ea1aa`.
The raw IDs and private artifact path remain restricted.

## Sixth full Bite 4 run — INCONCLUSIVE before custody verification

Sol executed the sole sixth user-authorized run with the T038 frozen harness,
helper and test hashes, pinned SDK 0.2.153 / CLI 2.1.273, and image ID recorded
in `verification.md`. It exited 2 with INCONCLUSIVE. The positive arm reported
`effect-or-observer-uncertain` and
`quarantine-container-preserved-for-custody-review`; the negative arm was not
run (`positive-release-candidate-not-established`).

The source SDK phase returned. The external observer saw the source running,
then recorded stop and removal with the durable intents. Only after source
removal did the harness create the target-state volume. The first custody COPY
helper failed at `_manifest_summary(args.source)`: its Docker exec returned 1
with `RuntimeError: two-domain file size limit exceeded` at the then-configured
64 KiB per-file limit. This happened before copy verification, linked
pre-release history custody, release, target container creation/start, or the
negative arm. At this sixth-run checkpoint, the public relative path was
unknown; T040's later metadata-only scan found the oversized config JSON
without reading its contents. This is a size-bound refusal, not evidence of a
history mismatch. The T040 scan did not itself change the original manifest
limit.

Quarantine stopped and preserved the copy helper. Two run-owned volumes
(source and target state) and one Exited helper remain, with zero running
containers. At the end of this sixth-run checkpoint, aggregate inventory was
seven engine volumes (six source-state, one target-state) and four stopped
containers (two Created, two Exited). No cleanup or retry occurred. This
checkpoint preceded the later T040 metadata result and conditional
authorization for one seventh full run. Bite 4 is not complete, Bite 5 remains
pending, and production remains unsupported.

Private artifact SHA-256 values: sanitized report
`2cca888a2b65170087c500432a7c7a6c26eacdd58509dff3774b8c0ae05db84d`, stdout
`ccc773ab9cbc36157388e32d232cbe2b4305be249082d81ab900c92ec9d3eb9d`, empty
stderr `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
abort ledger `d0e98156493112d2b17642c5fee39cc41efb46f3bcaf4b315ffe22a0147d6121`,
and private artifact manifest
`7711540cb5e09a7f5ccb4be6e61658624ba4086efde827ddbdb93c0902e2e25e` (16
files independently matched; mode 0600). Private paths and raw runtime IDs
remain in Sol's restricted record.


## T040 stat-only source-volume metadata scan — PASS

Sol ran the separately authorized repository runner once against the sixth
attempt's preserved source-state volume. The metadata container started,
captured the report, and exited 0. Its sole `/evidence` mount was read-only
with `volume-nocopy`, and the scanner read metadata only; no SDK, runtime,
history contents, custody, release, or target was involved. It reported nine
files, 14 directories, 394,590 total file bytes, and a maximum file size of
306,896 bytes for one config `.json`. No path or file content appears in the
public projection.

The diagnostic container and artifacts remain preserved. Current inventory is
seven engine volumes and five stopped containers, zero running. The metadata
container adds a stopped container; the source volume's data contents remain
unchanged, while its engine attachment metadata changed for the read-only
mount. There was no cleanup or repeat invocation.

Private SHA-256: artifact manifest
`aa3c4c235afa931507b6dedd28939e43e97c1cd212901c48c7d2150ec016499d`, public
JSON `af7b84e3145e6596044d767c164ca0ddec573ae25c93a1d2ba886de96f22ab68`, and
private JSON `c0f0b0a74d970562782cff6106aeb29fdf1d4b6768d70798c2e34a65df29e0f2`.
Raw IDs, names, and host paths remain in Sol's restricted artifact record.
The scan identifies a fixture-tree sizing issue; T041 changes only the whole
fixture-tree file/aggregate bounds and preserves the history-prefix and
history-discovery bounds. Bite 4 remains INCONCLUSIVE and Bite 5 remains
pending.

## T041 fixture-tree sizing correction — offline PASS, no runtime

The separate fixture-tree budgets are 512 KiB per file and 2 MiB per tree.
The same traversal defaults cover manifest, copy/re-manifest, pre-release and
final custody, and target prestart. History-prefix evidence remains bounded at
64 KiB and history discovery at 512 KiB. The focused synthetic suite covers
the T040-measured 306,896-byte config JSON through exact copy and custody,
mutated config during final history checks, exact and cap+1 file/tree sizes,
and the unchanged history-prefix refusal.

Astra's architecture review passed. Sol's canonical
`tests/run.sh --parallel-safe -k two_domain` gate passed **144 selected tests,
0 failures/errors/skips in 14.434s**. Frozen hashes: native probe
`a0379e325db46d599d5e3d98c3b25f4200036ae8e08eb1a618d43d59d4f5b069`, harness
`9f8a71fe30e370e6569bf7db2ec2466cb9338ca8aa89a001f39215a32f1de28c`, tests
`fa29dffec7c86131152dcee8b116e02f2a772130177d3d4fb25cb406a915b6b5`.
Private gate digests: stdout
`cecc5ecbbd849fe2a7ae66e63728eaf45fbc7a580130c3a553fe472af2283356`, stderr
`e8e31f13e4582ffc1e0a2ce36474cdd0547620d2020024e5c8e9af934dfe9847`, JUnit
`a4d994ae3288ceb50023edb79e408e22d73954c7664aa2e3f12a4ec0386ff8a8`.

Before the seventh attempt, Sol's fresh read-only preflight passed with seven
volumes, five stopped containers, and zero running. That one run has now
executed and is recorded below; no additional attempt or cleanup is authorized.
Bite 4 remains INCONCLUSIVE and Bite 5 pending.

## Seventh full Bite 4 runtime — arm INCONCLUSIVE; report packaging FAIL

Sol executed the separately authorized command once. The outer process exited
1 because `_assert_no_private_values` reported `private-identifier-in-report`.
The immutable full image ID was intentionally published at
`identities.image_id` and also appeared in the private input set because the
user supplied that digest as `args.image`. This is a packaging false positive;
the private arm result is INCONCLUSIVE, not a runtime FAIL.

The positive arm observed source stop/exclusion, exact source-target copy,
identity-linked pre-release parent-history custody, durable release, target
startup/stop/removal, and final custody. The parent UUID matched, with no
parent/child messages, history-read failure, or protocol errors. One native
task event was observed at target startup, so the sticky gate skipped the
history query. The positive arm reason was `startup-task-event-observed`,
`release_candidate_ready` was true, and `cleanup_complete` was false. The
negative arm was not run. The task event means the evidence does not satisfy
Bite 3's PASS criteria; this does not decide Bite 5.

Two new volumes remain preserved; no seventh-run containers remain. Overall
inventory at the seventh-run checkpoint was nine volumes and five older
stopped containers, with zero running. There was no cleanup or retry, and no
eighth attempt was authorized at that checkpoint.
Private artifact SHA-256: manifest
`537b3741de9c42e6ba9428f343d22a68e3196556e3755107a0c468f4e756902e`, report
`3db0840883f58d5dfd88fe727cb29e0df7e8977cd7c126f84ffdffb7dee025e9`, stdout
`e2ef15dee6b3b6884d6d36fb1d237d3ff862be6448a055512650ad683683bbed`, arm
result `6cee6803105e5668c166a340660624d99050e5df292f5c3b939502c2c0df30c5`,
release ledger
`44d97078a835f12ddb7931f4e79778ed81a4da34f22df5efd4f71ce1fbd80807`, and
target-launch ledger
`8024b9967ee5f20fc5a103e6b191cc81f91f7c974f0d2e4301266a8e0db4a6f8`.
All 37 restricted artifacts were mode 0600. Raw IDs and paths stay private.
The future-only sanitizer and startup-task lifecycle snapshot corrections
passed Astra review and Sol's `tests/run.sh --parallel-safe -k two_domain`
gate: 151 tests, zero failures/errors/skips in 9.749s. The snapshot captures
allowlisted target startup events before the optional history query and does
not change the sticky query refusal. Frozen code/test hashes and private gate
digests are in `verification.md`. This offline gate did not itself authorize
an eighth attempt; its separate authorization and result are recorded above.

## 2026-09-22 v1 experiment scope

The approved [stop-then-resume decision](../../openspec/changes/separate-swap-ctx-handoff/stop-then-resume-decision.md)
creates a separate experimental mode. Its experiment must defer target process
creation until explicit release, preserve a saved edit, exercise an unfinished
native child and tracked shell, and refuse unknown effects. The older harness
starts a target in its held phase, so its results do not establish v1 ordering.
See [the experiment contract](contracts/stop-then-resume.md).

Current pre-experiment audit: SDK `0.2.153`, bundled CLI `2.1.273`, SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`.
The existing harness is credential-free, network-isolated and bounded, but
its tracked sleeper/PGID observations do not prove complete host writer or
external-effect exclusion. Harness-enforced termination must be recorded
separately from native lifecycle stop. Authenticated acceptance and production
activation remain unverified.

### Executed v1 diagnostic: ordering demonstrated, restoration inconclusive

Sol executed three arms from a frozen candidate after **113 focused tests
passed**. All used the pinned SDK/CLI above and existing immutable image
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`.
Each container had network disabled, read-only root, dropped capabilities,
no host mounts, bounded resources, a sterile environment and only a dummy key.
Only its own disposable container was removed. Reports were private (`0600`
inside `0700` directories). No real account or installation was changed.

| Arm | Release boundary | Target created | Observation |
| --- | --- | --- | --- |
| Explicit release | Persisted before launch intent and process creation | Yes | Same parent session UUID observed; history query skipped on `startup-task-event-observed`; exact restoration inconclusive |
| Explicit release plus unknown effect | Refused; no persisted authorization | No | `unknown-effects`, with otherwise-valid source baseline; refusal demonstrated |
| Release withheld | Not authorized | No | `explicit-release-required` |

Each arm made four **source setup** requests to the scripted local endpoint,
zero observed source-drain requests, and zero target requests. These were
settled-parent cases with an unfinished native child and tracked shell, not
busy-parent or actual quota-limit tests. The continuous control-entry epoch
was not enabled in these runs; do not claim a full-interval zero-request proof.

Native interrupt receipt, current child/tool terminal evidence and tracked
sleeper exit were observed. Parent exclusion was **harness-enforced**:
`harness_cleanup_facts.pg_kill_observed` is true. The separate
`stop.forced_cleanup: false` concerns tracked-tool cleanup and does not prove
the parent exited naturally. Source coverage remains `tracked-fixture-only`.
Complete host/supervisor/escaped-writer exclusion is unproven.

The deterministic saved edit remained unchanged, SHA-256
`8b37cb1112307d5fc9b61b2cf1b8afaf9770a96ba5fe54de3db7069046e48889`.
The resumed target emitted the same parent **session UUID**, while source and
target result-event UUIDs differed as expected. A native task event appeared
during startup, so the probe sent no additional history query. This does not
establish whether that event represents replayed history or live restored work.
Parent history retention and exact loader proof remain unknown; child history
remains unverified. Every arm retains `verdict: inconclusive` and
`support_claim: false`.

Use the `stop_then_resume_v1` subrecord for this mode's conclusion. The generic
harness envelope also carries old strict-mode/unselected orphan-clear and
held-target assessments; those are not v1 acceptance requirements. The probe's
`released` phase means its explicit diagnostic boundary crossed, not that the
production lifecycle or full restoration contract passed.

Private artifact basename: `openrepotools-sol-v1-final.7cLFa6` in the bench
temporary directory; `commands.txt` retains exact invocations. Positive-arm
report SHA-256:
`99ee1126314b327606e78f39dab39cab9871e6db334fd406c21c18b50250305c`;
unknown-effect report:
`d99553afe66d5a219d8e5fc1c59747b5ad71ec0ce383e3578048c368c5e0c647`;
withheld-release report:
`fc101ad9851d731dae4e78fa427dfe07d5858d47dc87f592db3d8f911ff3d352`.
Artifact manifest SHA-256:
`2eab3112a74b9f551a94612bc78ba78adcb53f5827e08fb20a28bd18e208bf52`.
An unchanged, manifest-verified durable copy is preserved under
`${XDG_STATE_HOME:-$HOME/.local/state}/openRepoTools/diagnostics/openrepotools-sol-v1-final.7cLFa6`.

Implemented surface: `tests/probes/managed_native_loopback.py --mode
stop-then-resume-v1`, with `--explicit-release` and optional `--unknown-effect`.
The existing `--release-target` has different semantics and cannot be combined
with v1. **This is a probe option, not a public `lane-swap` mode.** Public v1
preparation/release/recovery, complete source-domain evidence and child/history
reconciliation remain outstanding. No new target-held/orphan-clear obligation
is imposed on v1 by this inconclusive result.

### Startup-event/history follow-up: measured preservation, unresolved recovery

The final follow-up passed **137 focused tests** before one explicit-release
arm ran against the same SDK `0.2.153`, CLI `2.1.273` and immutable image above.
Isolation and cleanup were verified again: dummy credentials, no network or
host mounts, read-only root, bounded resources, and removal of only the owned
sandbox. No other runtime arm, real account, install or busy-parent variation
was run in this follow-up. Previous negative/withheld arms remain historical.

Source events were `task_started`, `task_progress`, `task_updated`, then
`task_notification/stopped`. The target emitted one startup
`task_notification/stopped`. Its session/task digests match source terminal
observation 4, but its tool-use ID is absent where the source supplied one.
Neither event supplies an agent ID, and their event UUIDs differ. The recorder
uses the immutable source terminal as its comparison reference and reports
`live-or-unresolved`; the matching task/status does not prove complete recovery
or no pending work. Different UUIDs alone do not establish that classification.

History is discovered under the pinned runtime's `config/projects/<project>/`
layout, with bounded no-follow regular-file reads and structural metadata only.
Each prefix comparison covers the complete accepted earlier file, not just its
first few kilobytes. Reads exceeding the 64-KiB per-file cap remain unknown.

| Boundary | Parent, observed session link | Candidate child, unattributed |
| --- | --- | --- |
| Active source → source excluded/pre-release | 52,974 → 52,974 bytes; content unchanged | 7,562 → 32,580 bytes; original 7,562-byte prefix preserved |
| Pre-release → post-startup, before query/cleanup | 52,974 → 55,317 bytes; original 52,974-byte prefix preserved | 32,580 → 32,580 bytes; content unchanged |

These observations establish bounded storage preservation only. The child file
does not have a proven native identity join; neither row proves loaded context
or resumed execution. The saved edit remained unchanged. Exact parent session
identity was observed, but the startup event kept the extra history query
blocked (`history_query_count: 0`), so restoration remains **inconclusive** and
`support_claim: false`.

The scripted endpoint received four source-setup requests, zero source-drain
requests and zero target requests. The continuous control-entry epoch and busy
arm were not enabled; this is not a full-interval no-inference or quota test.
Native interrupt/child/tool terminal facts remain separate from
`pg_kill_observed: true`: the harness excluded the parent, and
`source_termination_task_completed: false` forbids calling termination task
completion. Source scope is still `tracked-fixture-only`.

Durable private evidence:
`${XDG_STATE_HOME:-$HOME/.local/state}/openRepoTools/diagnostics/openrepotools-sol-t003-t004-sidecar.e63Nfv`.
`commands.txt` records exact invocations; copy manifests and private modes were
verified. Final probe/test/JUnit hashes are in [verification.md](verification.md).

- Runtime report SHA-256: `de026a8f6d175e0aef916cc209d0de809f59d1a9cfb6db9d6648fd0ff3be2f1a`.
- Lifecycle/history report SHA-256: `4eb95ab22fc7162d610d07a9c13ba4efab768ca97c26faba5550c998ac3a75bc`.
- Stop-facts report SHA-256: `768cffedc5d477373bdfa6587e5cd6734345fca6b3771c895510acb521d10684`.
- Artifact manifest SHA-256: `f616066d799bd6da4dfec016c3a3e057eea9096ee1d6a06de8bf4ed11352360e`.

Next required evidence is an authoritative source task/tool/agent-to-history
join and bounded post-release reconciliation that can account for startup work,
alongside a supported complete source-containment domain. Do not remove the
startup guard based on a matching stopped notification or preserved files.
Public preparation/release/recovery, native unenroll, broad regressions and
deployment gates remain outstanding.

## 2026-09-21 pinned-runtime feasibility audit (strict mode)

September 22 architecture recheck: Astra verified the same installed SDK
`0.2.153` and bundled CLI digest and found no supported producer for the
missing authorities listed below. The documented session-storage append/load
boundary records persistence but does not define durable orphan-ineligibility
or a correlated loaded-and-held receipt. OpenTelemetry export can drop spans
or lose buffered data on a crash, so it cannot certify a gap-free zero-dispatch
interval. A task-terminal event remains distinct from run completion. This
read-only audit ran no new account/model probe and makes no support claim.

Discovery references:
[Python API](https://code.claude.com/docs/en/agent-sdk/python#methods),
[session storage](https://code.claude.com/docs/en/agent-sdk/session-storage),
and [telemetry flushing](https://code.claude.com/docs/en/agent-sdk/observability#flush-telemetry-from-short-lived-calls).
These current documentation pages do not certify the pinned package. Native
ctx additionally needs its own entry-to-drained proof before shutdown; neither
swap metadata nor a later adoption receipt supplies that authority.

### Required runtime support for activation

The next compatibility decision needs supported observations with these
semantics; these are requirements, not invented runtime event names:

| Boundary | Required observation |
| --- | --- |
| Control entry | Start observation before preflight/fencing and cover parent, child, continuation, retry, and orphan dispatch attempts. |
| Run drain | Account for the sealed roster, pending admissions, tools/effects, and parent continuations independently of interrupt acceptance. |
| Durable worker state | Identify the persisted revision where stopped workers cannot autonomously resume or enqueue restart notifications; retain their history. |
| Held target load | Identify the exact parent UUID and loaded conversation revision, reconcile orphans, and hold all inference until explicit release. |
| Control exit | Provide an ordered, gap-free request-attempt count through the actual release boundary, with gaps/crash uncertainty explicitly represented. |

Each observation must carry the supported schema/runtime pin, process
incarnation, and monotonic sequence and join the existing operation,
lineage/session/invocation, interrupt, target, and release identities. Recovery
needs readback without replaying controls. Native ctx needs a separate source
entry-to-drain binding followed by a fresh held-coordinator receipt.

The [TypeScript control-response reference](https://code.claude.com/docs/en/agent-sdk/typescript#sdkcontrolinterruptresponse)
offers one bounded lead: `interrupt_receipt_v1` and
`interrupt_cancel_queued_v1` describe main-thread queued messages, excluding
subagent messages. Their documented version floors precede the pinned CLI,
but advertisement and behavior on the selected configuration still need
inspection. An empty receipt cannot prove run drain or orphan clearing.
Preserving a receipt is a possible adapter improvement; enabling queue
cancellation requires an explicit cancellation-policy decision. Neither
enables production swap by itself, and no SDK upgrade or runtime fork was
introduced by this audit.

Release options are to retain these guarantees and obtain supported upstream
observations/equivalents, or explicitly amend the product guarantees through
OpenSpec. The initial September 22 implementation request did not choose weakened
guarantees. The later v1 amendment above changes target ordering only for the
new explicit mode. Production providers remain disabled pending their own proof.
A narrower request
observation promise alone cannot settle unknown writer/effect or orphan state.

The user authorized implementing the parallel offline-integration and runtime
feasibility recommendation. This investigation does not authorize authenticated
account changes, installation, or enabling production capability.

Astra inspected the retained isolated Python SDK **0.2.153** package and
verified its bundled CLI SHA-256 still equals
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`.
The audit identifies three distinct unresolved authorities:

- **Worker/orphan clearing:** the package's
  `claude_agent_sdk/_internal/query.py::_track_task_lifecycle` explicitly
  distinguishes an empty tracked-task set from a completed run: a settled task
  can still have a pending parent continuation. It identifies a CLI run-boundary
  signal as necessary and does not accept the background-task snapshot as a
  complete inventory. `stop_task` acknowledgement and terminal notification
  therefore cannot supply durable worker/orphan clearing.
- **Exact held parent load:** `ClaudeSDKClient.get_server_info` returns cached
  initialization metadata; `get_context_usage` reports aggregate usage. Neither
  is an exact, correlated parent-load receipt before release. UUID/history
  observed after release remains a separate fact.
- **Continuous request observation:** the scripted loopback gateway counts
  arrivals within its own endpoint scope. That observation does not cover every
  runtime dispatch attempt or establish a production continuous observer.

Current [official Python API documentation](https://code.claude.com/docs/en/agent-sdk/python)
and [session documentation](https://code.claude.com/docs/en/agent-sdk/sessions)
were checked as discovery references, not as capability certification for this
pinned package. No SDK upgrade or undocumented runtime control was introduced.

Production provider wiring stays disabled until an authoritative supported
source supplies distinct, correlated durable worker/orphan-clear, run-boundary,
held-parent-load, and continuous-dispatch observations required by the existing
contracts. A run boundary alone does not prove durable state clearing.
An injected positive test response or a quiet probe interval cannot replace
those sources. This is an evidence-gap disposition, not an approved scope
reduction or an assertion that all possible runtimes lack these capabilities.

### Bounded positive-orphan probe

One no-auth probe ran on September 21 at 21:41:08–21:41:32 UTC with
`--control-mode positive-orphan`, without `--release-target`. The exact SDK and
CLI pins above and the existing image
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`
were retained. The disposable sandbox had no network, host mounts, or real
credentials; its source used only scripted loopback responses. No image was
pulled. Pre/post source, mode, SDK/CLI, and image checks matched. The owned
container was removed and independently confirmed absent.

The source had unfinished worker records before the requested owned-process
crash. Source-process-group and tracked-sleeper exclusion were observed after
the crash; forced cleanup is not graceful stop or durable state-clear evidence.
The target initialized with the source UUID and remained held without release,
with zero observed target loopback requests. Exact parent loading, persisted
record loading, orphan restoration, wake, and notification enqueue remain
unknown. The continuous control-entry epoch was not selected for this arm.

The report classifies the positive-orphan lifecycle surface as unsupported,
with `verdict=inconclusive` and `support_claim=false`. Silence does not establish
absence of wake or a production-wide absence of inference attempts. No task or
acceptance checkbox is closed. Private artifact
`openrepotools-sol-orphan-probe.53Wbay/report.json` has SHA-256
`e3bcf6fab21409417beb24e1591430ab63f94bda2c85deccbb2ad03d522890b5`.

## 2026-09-18 bounded busy-parent loopback observation

After explicit approval, one busy-parent run used the same disposable exact
SDK `0.2.153`, bundled CLI `2.1.273`, and required CLI SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`.
The frozen harness ran with `--control-mode interrupt
--busy-parent-before-control --release-target`; it did not use the settled
control-entry flag or repeat the orphan/crash arm. The existing local
`py-bench:brett` image had ID
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`.
The sandbox had `network=none`, no host mounts or real credentials, and used
only the scripted loopback endpoint and dummy key. No image was pulled. The
owned sandbox was removed, `sandbox_removed=true`, and no owned
`managed-loopback-*` container remained.

The gateway positively identified the pending parent **Agent** continuation
as request index 4. Immediately before control entry, the real child/task and
tracked Bash process were observed active with no prior terminal child event.
Under the gateway lock the barrier was pending and waiting, and the sticky
epoch began at index 5. This is the contracted
`immediate-pre-entry-not-atomic` liveness observation, not an atomic process
fact or a general busy-parent capability. The blocked response was released
after control but `response_completed=false`; that false value does **not**
prove cancellation or any other completion outcome.

The epoch crossed source, source-drain and target-held and closed at release.
Its `start_request_index=5` and `end_request_index=4` are the valid empty
range: zero new loopback `/v1/messages` arrivals occurred before release. The
separate release request was index 5, outside the closed epoch. This is only a
scripted loopback arrival observation, not zero-global inference or a
production continuous observer.

The interrupt receipt, stopped notification, tool terminal, tracked Bash exit
before cleanup and source process exit were all observed; forced cleanup was
false. The child Agent-header/task join remained false. The target was
requested to resume the source UUID, initialized and held with zero Messages
requests. `same_parent_uuid=true` is an aggregate that includes post-release
facts and therefore does not prove the exact parent was loaded during hold.
Exact held parent load, restored-task wake, worker-state clear and orphan clear
remain unknown, and the positive-orphan arm was not exercised.

After release, the request carried source/release markers and Agent tool
use/result history, and the target successful-result UUID digest matched the
source's observed session UUID digest. The interrupted source emitted no
successful result, however, so this does not prove completed-source
continuity. The report correctly records `eventual_continuity_observed=false`
with `continuity_scope=eventual-history-only` and reason codes
`target-parent-load-not-proven` and
`target-release-continuity-not-observed`.

The sanitized report is in private temporary artifact
`openrepotools-busy-parent.MfKev7/report.json`, SHA-256
`bd463d8fc4f0daa189b1cc11341e1f5309358dd2395e795a4c8c78cb2ed696b0`.
The eight-item source/probe/contract/SDK pin manifest has SHA-256
`1a24fea05c54b52053c9e551ac20f3a79650f6ea54469c8f0e0ed7facd97e42a`;
its pre/post comparison, image identity, SDK version and CLI version all
matched. The result remains `verdict=inconclusive` and `support_claim=false`.
It closes no task or acceptance checkbox and grants no public/runtime support.

## 2026-09-18 bounded control-entry loopback observation

After explicit approval, an exact SDK `0.2.153` copy was placed in a disposable
private environment and independently checked before one bounded run. Its
metadata artifact has SHA-256
`7eabac2bf2aaa90a695429eef92e1e5b097d005a09545611363ba22c897c77bb`;
the SDK selected bundled CLI `2.1.273` with the required full SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`.
The pre/post private-SDK manifest matched with SHA-256
`e889a8561914ecef5a03d1f1943a736467d537d8a06d69f04afcd58dbab7859a`.
No existing production interpreter was changed.

The frozen `managed_native_loopback.py` harness ran with `--control-mode
interrupt --control-entry-before-settle --release-target` against the existing
local `py-bench:brett` image. Its disposable child container used
`NetworkMode=none`, no host mounts or real credentials, a read-only root, all
capabilities dropped, no-new-privileges and bounded resources. No image was
pulled. The harness removed its owned container and reported
`sandbox_removed=true`; no owned loopback container remained.

The scripted source initialized and produced a native task, Agent header,
active Bash process and tracked sleeper. At actual control entry,
`parent_settled_at_control_entry=true`; the report classifies source-drain
causality as `settled-parent-before-control`. This observation therefore does
not exercise or prove an actually busy parent even though the observer was
configured to begin before the settlement wait.

The single observer epoch covered source, source-drain and target-held phases
and closed on release. Its scope is only scripted loopback `/v1/messages`
arrivals, not global inference or a production continuous observer. Four
source arrivals preceded the epoch. Its `start_request_index=5` and
`end_request_index=4` form the valid empty observed range: zero arrivals were
inside it. The separate release request was index 5, outside the closed epoch,
and brought the endpoint sensor's run total to five. The interrupt produced a
receipt, stopped notification, tool terminal, tracked process exit before
cleanup and source-parent exit without forced cleanup. Those coherent facts
remain a bounded interrupt candidate, not capability.

The target was requested to resume the source UUID, initialized, and held with
zero `/v1/messages`, count-tokens or API-hello requests. Exact parent load,
restored task events and wake evidence remained unknown; worker and orphan
state-clear facts remained unknown, and the positive-orphan arm was not
exercised. After the separately requested release, one `/v1/messages` request
contained source and release markers plus Agent tool-use/result history and
returned the same source UUID. The report classifies this only as
`eventual-history-only` continuity. It reports `verdict=inconclusive`,
`support_claim=false`, with `target-parent-load-not-proven`; no public or
runtime capability follows.

The sanitized report's private temporary artifact basename is
`openrepotools-native-loopback-runtime.cyIjNi/report.json`, SHA-256
`fd329c35d988ecf0574d25ae06c8f3b5882e0c669b42a1abbcfe88f169fa6dec`.
The corresponding private log SHA-256 is
`aac8b025a0b350aec3bc561dbf263de4d0af9612509e31a92b1323b4b5607d85`.
All 45 frozen source, test, probe, contract and design files had identical
pre/post manifests with SHA-256
`2d000da7f0cebd551b719d0a6cc849023f42eb1c43f9168094357b573bc8f3f0`.
This bounded observation closes no task or acceptance checkbox.

## 2026-09-18 Stage 1 follow-up

The bounded follow-up and artifact hashes are in the
[runtime-boundary investigation](../../openspec/changes/separate-swap-ctx-handoff/stage1-runtime-boundary.md).
The isolated SDK was recovered after the bench restart; its selected bundled
CLI digest again matches the reference below. A fresh baseline reproduced
initialization with no credentials and acknowledgement of a nonexistent task
without a terminal notification.

The reproducible probe now offers `--case missing-parent-resume`. It derives
the exact resume argument through official SDK options, selects a fresh UUID
in an empty sandbox, and sends initialization only. On the selected runtime it
produced a missing-parent loader error and natural exit 1 before successful
initialization, with no transcript writes. The requested UUID was echoed in
the error frame; that echo alone is not restoration evidence. The focused
probe checks passed **25 tests**. Positive parent restoration and model
dispatch remain unproven by this negative control.

The additional native-worker experiment uses a **scripted loopback Messages
endpoint** and a dummy fixture key in the same `network=none` sandbox. This is
gateway/API-key mode, not the `tokenSource: none` baseline. It can exercise
real native runtime task creation and stopping without a real account or model
service. It must keep source setup, source stopping, and target-held request
counts separate and report task, tool, process, transcript and loader facts
independently. Its result cannot grant subscription-account or CCR support.
The selected CLI's stream-json protocol is exercised directly with SDK-derived
arguments; that is not the full Python SDK client or public lane workflow.

The first corrected run observed a real background Agent/task, a live Bash
process, and native task/transcript writes. `stop_task` for the actual task
produced separate receipt, stopped-notification, tool-terminal and process-exit
facts before parent teardown. The target then initialized with the exact
source UUID and held for eight seconds with zero endpoint requests. No target
session UUID was emitted during that hold, so exact loaded conversation was
still unknown. One Messages request arrived during source stopping; this run
does not prove the required zero-request account-control interval. Internal
orphan restoration/notification enqueue remain unobserved, not certified
absent.

The settled-parent repeat still emitted one source-control Messages request
for `stop_task`, but the documented coordinator-wide `interrupt` comparison
emitted **zero** while producing native stopped, tool-terminal and sleeper-exit
evidence before teardown. Its exact-resume target held for eight seconds with
**zero** endpoint requests; after explicit release, one request carried the
original source/Agent history and its successful result returned the same
session UUID. This establishes eventual native continuity independently of
the held interval's request count.

The final crash-left-unfinished control preserved native records, excluded its
observed source/sleeper processes by identity, and resumed with zero held
requests and preserved UUID/history after release. It does not establish a
positive CCR orphan-wake/classifier path. Both final targets emitted one
native task frame during hold; internal restore/enqueue remain unknown. All
disposable sandboxes were removed.

Astra accepts coordinator interrupt as the next bounded integration candidate
for this selected CLI and scripted API/gateway mode. It needs a governed
whole-roster authorization and durable drain contract; it must not replace
task-specific `stop_task` invisibly. Actual profiles/accounts, busy and
multiple-child paths, complete lineage/effect accounting, native child exact
continuation and persistent inference fencing remain unverified. T003, T004
and T030 stay open, and production capability remains disabled. See the
investigation record for frozen sources, report hashes and validation limits.

The follow-up design is now specified in
[coordinator-interrupt.md](contracts/coordinator-interrupt.md). Acceptance must
measure the entire interval from account-control entry before preflight, not
only Stage 1's settled-parent cancellation window. It must also cover active
parent turns, multiple/nested children, completion races, event gaps, lost
receipts and source-writer/effect uncertainty in the actual supported modes.
The contract and fake-runtime tests do not supply that live evidence.

## 2026-09-17 isolated initialization observation

The earlier shared-network probe container was inspected and confirmed exited,
with process ID zero. A fresh disposable container successfully used literal
Docker `NetworkMode=none`, no host mounts, a read-only root filesystem, all
capabilities dropped, no-new-privileges, resource limits and temporary writable
directories. No shared-network workaround was used. An initial executable
placement failed because the temporary mount was non-executable; that sandbox
was stopped and replaced before the observation with an explicitly executable
temporary binary directory.

The SDK was resolved from its existing isolated probe environment, not installed
into the production interpreter. SDK `0.2.153` selected its own
`claude_agent_sdk/_bundled/claude` through the installed transport's bundled-first
resolver. The full selected executable digest was recomputed:
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`.
A byte-identical copy in the disposable container reported `2.1.273 (Claude
Code)`. The SDK-selected command shape was:

```text
<selected-cli> --output-format stream-json --verbose --system-prompt "" --input-format stream-json
```

The observation executed those arguments against the copied selected binary;
it did not exercise the whole Python SDK client lifecycle. The child received
an allowlisted environment, empty home/config directories and exactly one
`initialize` control request. No user-query frame was sent. During the bounded
eight-second read it returned one successful `control_response`, reporting
account `tokenSource: none`; stdout contained 15,498 bytes and stderr zero.
Only sanitized frame types and token-source classification were retained in
this report. The child was terminated and reaped (return code 143); a process
listing showed only the sandbox's sleep process, and the sandbox was then
stopped and confirmed exited with process ID zero.

**Verdict: inconclusive; support claim: false.** Initialization is the only
case exercised. Model dispatch was not independently instrumented and remains
unknown. Positive orphan restoration and the supported terminal-stop/clear
candidate were not exercised. Static inspection of this exact binary found
that the ordinary structured-input transport starts with null restored worker
state, while the CCR worker-state path needs authentication headers. Neither a
silent startup nor that static distinction proves the required positive
control. The reason for withholding support is
`orphan-positive-control-unreachable` in the current no-auth harness, not an
observed successful hold boundary or proof that every runtime mode is unsafe.

The baseline is now reproducible with
[`tests/probes/managed_gate0.py`](../../tests/probes/managed_gate0.py). Run it
inside the declared bench, naming an existing isolated SDK interpreter, an
existing local bench image and a new private report path:

```sh
python3 tests/probes/managed_gate0.py \
  --sdk-python "$PROBE_SDK_PYTHON" \
  --image "$PROBE_BENCH_IMAGE" \
  --output "$PROBE_REPORT_PATH"
```

The harness never pulls an image, mounts host directories, loads real profiles,
or sends a user query. It checks the SDK-selected argument shape, verifies the
copied executable digest, rejects shared-network or weakened container
isolation and removes only its own container. Report paths are created
exclusively with mode 0600. The successful harness run reported the same
SDK/CLI/digest, successful no-token initialization and
`sandbox_removed: true`. Its **inconclusive** report is an observation artifact,
never a production capability grant. Isolation validation has 13 passing
offline tests, including rejection of the previous shared-namespace pattern.

Next evidence required: a supported way to exercise the relevant orphan
restore mechanism in isolation, independently observe wake and model dispatch,
and observe terminal-stop/state-clear through supported runtime operations.
Do not add credentials, undocumented flags or transcript rewriting to turn
this baseline into a passing result. T003/T004/T030 remain open until their
complete acceptance requirements are met.

This is a measurement plan, not authorization to access an account, start or
stop a session, switch a profile, send a prompt, or modify a worktree. Reading
or editing this file authorizes none of those actions, and this documentation
change performs none of them. A separately approved run may use only disposable
profiles, sessions, and directories; without that separate approval the gate
stays `UNVERIFIED`. Fake adapters and synthetic lifecycle events cannot satisfy
this gate.

## 2026-09-17 missing-task stop control

The probe now follows successful initialization with the documented
`stop_task` control for `gate0-nonexistent-task` in its empty disposable runtime.
It creates no child/task record and sends no model query. This is a negative
control for acknowledgement semantics, not the required positive orphan or
real-child terminal-stop experiment.

On the same SDK `0.2.153`, selected CLI `2.1.273` and full digest recorded
above, the runtime returned **success for the nonexistent task**, followed by
**zero matching terminal notifications** during the bounded observation.
The sandbox was removed and the child reaped. Evidence is retained externally
at `py-bench:/tmp/managed-gate0-stop-control-20260917.json`.

This directly demonstrates why a control acknowledgement cannot prove child
quiescence or durable worker-state clearing. The SDK's documented
[`stop_task` method](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/client.py)
also describes a separate stopped-task notification; the installed version
was inspected before the probe. The capability result remains **inconclusive**,
with no production grant. All **17** probe isolation/observation tests pass;
they explicitly prevent even a synthetic terminal notification for the missing
task from being recorded as proof that a real child stopped.

## Scope and non-authority

The future run, if separately approved, must use the implemented public path
and the exact pinned native runtime configuration. It must not adopt, stop,
repoint, or inspect private data from an existing user session. It must not
create a written handoff as part of swap or worker restart. A user-requested
`handoff` remains a different operation and is not evidence for this gate.

No account names, credentials, tokens, raw environment, complete transcripts,
checkpoint contents, or private tool output belong in the result. Record only
sanitized identifiers, hashes, statuses, capability facts, and bounded process
or hook observations.

## Gate 0 — pin the actual runtime and startup behavior

Before any authenticated or model-bearing scenario, record the exact SDK
package/version, selected Claude binary path as an external observation,
binary version, full SHA-256 digest, runtime mode, platform, Python version,
launch settings, and profile/store configuration. The path and full digest
must be captured from the executable actually selected by the SDK; do not
substitute a system binary or a remembered version. The prior 2.1.270
system-executable trace is informative only. The measured candidate is SDK
0.2.153 selecting its bundled 2.1.273 executable; that observation is not a
passing capability result until its exact path, full digest, and mode are
recorded for the run.
The measured bundled digest was
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`; retain it
only as a probe reference and recompute/record the selected executable digest
for every future run.

Run a no-auth, no-model, disposable orphan fixture using that exact selected
runtime. Gate 0 must establish, from the actual pinned binary rather than a
fake runtime:

1. which startup mode is being tested (interactive takeover versus SDK
   `stream-json`/the `print.ts` path);
2. in a positive orphan case, whether a deliberately seeded durable native
   parent/task record is loaded, a notification is enqueued, a child/parent is
   woken, and a model-query attempt occurs—each as a separately observed
   outcome;
3. in the target safety case, after a supported source stop has produced
   terminal child/tool evidence and durably cleared the old
   `running_background_tasks` state, whether target connect with inference
   fenced reports terminal-cleared state, no orphan restored, no orphan
   wake/notification, and no model query; and
4. whether native lifecycle and hook/tool evidence remains correlated after
   startup.

The positive orphan case intentionally distinguishes
`enqueuePendingNotification`, a wake, and a model request; a no-auth failure
or eventual `idle` result cannot collapse them. A held connection is not
evidence of child continuation. Interactive takeover and SDK `stream-json` are
separate modes: interactive takeover may provide an
autoresume callback, while the `print.ts` path has no autoresume callback. The
result is valid only for the exact SDK, selected binary, version, digest, mode,
and platform tested. If the selected mode is proven non-auto-resuming, its
safety boundary is direct current-run native child/tool quiescence and
containing-process exclusion; do not require or invent a classifier marker
solely to suppress an absent callback. If the target criterion or applicable
non-auto safety boundary is not proven, mark the configuration `unsupported`.

The selected 2.1.273 print/stream path may restore persisted
`running_background_tasks` as `restoredOrphans`; its default-enabled
`tengu_ccr_orphan_restore_wake` may call `enqueuePendingNotification` and
trigger inference before an external query. Gate 0 therefore must prove
terminal child/tool stop and durable clearing of the old running-task state,
then prove that target connect emits no orphan wake and no model request.
Stream-json/print mode by itself is insufficient. If this evidence is missing,
the selected configuration is `unsupported`.

## Gate 1 — discover one native lineage

Use only a separately approved disposable lane. Start one coordinator and the
native child kinds under test through the public runtime. Capture the
coordinator's exact:

- native `session_id`, selected profile/account identity, and transcript/store
  reference;
- runner PID/start identity, containing process tree/process-group evidence,
  and current process-domain observation;
- bounded native `session_name` and canonical `bound_lane`; and
- model, effort, effective permission mode, tools, launch settings, and
  runtime incarnation.

Capture each child only as a native lineage record. It must include
`agent_id`; record `task_id` only when an actual native task event or
authoritative native task record supplies it. Also capture exact `type`,
`tool_use_id`, direct parent linkage, transcript/task record and child-store identity, current `status`,
`stop_provenance`, model, effort, immutable custom-agent definition identity,
and effective tools/permissions. A native child receives no invented session
UUID, top-level runner ID, or process-group ID. An OS process observed beneath
the coordinator is process-tree evidence only, not a child identity.

These fields must be assembled only from actual SDK fields and durable joins.
`SubagentStart` carries `session_id`, `transcript_path`, `cwd`, optional
`permission_mode`, `agent_id`, and `agent_type`; `SubagentStop` adds
`stop_hook_active` and `agent_transcript_path`, but neither supplies
`task_id`, `tool_use_id`, or `parent_agent_id`. Tool hooks carry
`tool_use_id` and may carry `agent_id`/type. `TaskStarted`, `TaskProgress`, and
`TaskNotification` carry `task_id`, `session_id`, event `uuid`, optional
`tool_use_id`, and `TaskStarted` also carries `task_type`; `TaskUpdated` carries
`task_id`, `status`, `patch`, and optional `session_id`/event `uuid`, but no
`tool_use_id`. Session history may supply `parent_tool_use_id` and
`parent_agent_id`. Join a durable pending Agent admission to these fields and
the current parent invocation/watermark; a pending admission may join an
actual task ID but cannot create one. A missing or ambiguous join is
`unresolved`, including a nested child whose parent cannot be established.
The task-event `uuid` is transport correlation, not a per-child UUID.

Record the containing process tree and actual hook/tool facts. Hooks must show
the coordinator identity and, where applicable, the exact child `agent_id`,
`task_id`, and `tool_use_id`; an event without an agent ID cannot be assigned
by name or timing. Tool facts must include start/end/failure, descendants,
and possible external effects. Keep parent process-tree ownership distinct
from native child identity.

### Gate 1a — child permission and ownership edge

Exercise a read-only coordinator with one explicitly authorized writable
native child. Bind that child's hook/tool decision to its actual `agent_id`,
immutable custom definition, effective permission mode, allowed tools, and
writable path. The parent `read_only` setting must not make the authorized
child read-only, and the child must not inherit broader permissions than its
own definition. Because any member may write, the coordinator execution
lineage must hold the workspace/worktree claim; an isolated child worktree
uses an additional path claim owned by that same lineage.

Then exercise an unknown child ID, missing definition, contradictory policy,
or ambiguous hook/tool record. Admission must refuse before that child can
write, without broadening the parent or releasing the lineage claim. Record
this as `unresolved`/refused, never as a read-only success.

## Gate 2 — seed and observe the lifecycle ledger

Using only the separately approved disposable prompts, establish unfinished
native tasks and at least one completed child. The ledger must consume and
correlate these actual event kinds:

- `SubagentStart` and `SubagentStop`;
- `task_started`, `task_progress`/`progress`,
  `task_notification`/`notification`, and `task_updated`; and
- `PreToolUse(Agent)`, `PostToolUse(Agent)`, and other tool hook events.

`PostToolUse(Agent)` closes only the Agent launch tool. It is not child
terminal evidence; a child that remains active after that call remains active.
Terminal status requires a correlated `SubagentStop` or an authoritative
task-terminal update. A stale status/notification from an earlier event
watermark cannot terminate the current task.

The runtime may reuse an `agent_id` after a child resumes. Bind terminal
evidence to the current actual `task_id` when supplied, direct parent
invocation/`tool_use_id`, and monotonic event watermark. Verify that a reused ID starts a new ledger
incarnation rather than allowing an old completion notification to mark the
new run complete.

## Gate 3 — stop provenance, background work, and effects

Perform the bounded stop while an unfinished child and, separately, a tracked
tool are active. Observe the durable fence, event drain, tool end/failure,
containing process-tree exclusion, and retained lineage claim. Record the
actual stop provenance: model stop, user cancel, SDK cancel, parent shutdown,
runtime failure, process loss, or unknown. An interrupt receipt, parent exit,
OS suspension, background flag, `setsid`, or `nohup` is not quiescence.

Test a runtime-owned native background subagent as its own participant kind.
Its native task ID, parent linkage, lifecycle events, process-tree relation,
and hook/tool policy must remain observable after the Agent launch tool ends.
Do not mark it stopped or complete merely because that launch call returned.

Test an unmanaged detached shell/process separately. If it lacks native task
and lifecycle ownership, or a remote/external effect may have happened, the
result is unknown: retain the lineage claim and fence, refuse release, and do
not replay. A background marker or parent exit cannot turn it into a controlled
native child.

Test native teams in a separate scenario and report them as a separate
participant type. Coordinator resume or ordinary subagent evidence does not
prove team restoration. Teams remain `unsupported` until their own exact
runtime, lifecycle, process, permission, and store behavior passes a reviewed
probe.

## Gate 4 — cross-profile preflight and exact restoration

For a separately approved source/target profile pair, compare canonical
profile identity, expected account identity, transcript family,
coordinator store, project/workspace, and every native child store. A shared
family label is not enough: if the child store is profile-specific, require an
actual tested source-to-target mapping preserving parent session, agent/task
IDs, type, launch tool, transcript record, status, stop provenance, model,
effort, custom definition, tools, and permissions. A missing/divergent or
untested cross-profile child store is `unresolved`/`unsupported` before stop.

After safe source quiescence, restore the exact coordinator `session_id` with
the official loader under the target account and keep it held. Verify its
account, process, name, lane, permission, model/effort, workspace, and
launch-definition evidence. During this control phase, accepted-send/query
counts must show no model request, generated checkpoint, continuation prompt,
semantic summary, commit, push, or written handoff.

Mark a native child `resume-pending` while held only when safely stopped SOURCE
current-run evidence, exact target parent restoration, and the tested pinned
resumability capability all agree: correlated `SubagentStop` or authoritative
task-terminal evidence, terminal tracked tools, source process exclusion, and
reconciled effects; the same parent; captured `agent_id` and actual native
task-record/event `task_id`; matching parent invocation, immutable definition,
model/effort, accessible transcript/store, tools, permissions, stop
provenance, and current event watermark. No held/active continuation event is
required or accepted before release. After explicit release, a current
correlated continuation event under that same parent/invocation/watermark
changes the disposition to `exact-resumed`. No child UUID or PGID is needed or
permitted.

If user/SDK cancellation or in-process loss is not documented and tested as
resumable, do not call the child exact. Preserve its records as
`restart-pending` when a mechanically composed restart is possible, or
`unresolved` when identity/effect evidence is incomplete. An inaccessible
child transcript/store blocks exact continuation, including `resume-pending`,
but does not alone block a safe `restart-pending` fallback when current-run
stop/effect facts and the original parent/native task record, model/effort, and
custom definition are recoverable. Unknown effects remain unresolved. A new
parent process alone never proves exact child continuity. Completed children
remain complete and are not resumed or replayed.

## Gate 5 — release-gated restart fallback

For each `restart-pending` child, first establish target coordinator readiness
and an explicit matching `release`. Only then may the coordinator receive the
ordinary model instruction that uses the durable task/identity record. This is
model-assisted worker restart, not a generated semantic handoff. The accepted
transport acknowledgement is not evidence that a child restarted.

Record `restarted` only after a correlated native task/start/lifecycle event
proves that the new run was created under the intended parent and definition.
If the runtime assigns a new `agent_id`, retain the original ID as the source
record and link the new ID as a new run; do not claim the old conversation or
identity was exactly resumed. If no correlated event arrives, retain
`restart-pending` or mark `unresolved`; never infer success from the model's
text or from a sent instruction.

The control phase may not send this instruction before release and may not use
the exhausted source account as a prerequisite. The fallback produces no
written handoff and does not replay completed work or uncertain external
effects.

## Gate 6 — partial start and retry

Inject a target-start failure after the coordinator and at least one native
child have reached held readiness, and separately after a child restart
instruction might have been sent. Keep the same durable operation identity.
On retry, reconcile the target coordinator process/tree, native child/task
records, event watermark, stores, hooks, tools, claims, and effects before any
new admission.

The expected result is per child, not all-or-nothing narrative:

| Result | Required proof and retry behavior |
| --- | --- |
| `resume-pending` | Safely stopped source current-run evidence, exact restored parent, actual native identity/task record, definition, and pinned-runtime predicate agree while held; no continuation event is accepted before release, and the post-release event is required for `exact-resumed`. Do not start a duplicate child. |
| `exact-resumed` | After release, a current same-parent/captured native ID continuation event and definition match prove exact continuation. Do not start a duplicate child. |
| `restart-pending` | Durable stop/task record exists but no exact continuation or correlated new run yet. Do not dispatch before target readiness and release. |
| `restarted` | A post-release instruction has a correlated native start/task event. Do not send the same restart again automatically. |
| `unresolved` | Any missing/contradictory identity, stop, policy, process, store, or effect evidence. Keep the fence/claims and require explicit reconciliation. |
| completed | Preserve completed state. Never replay or restart it during target retry. |

Verify that retry never creates a second parent owner, duplicate native child,
duplicate writer, duplicate tool effect, or automatic resend of uncertain mail
or external actions. A partial target start must remain visible and recoverable;
it is not permission to fall back silently to the old account or a handoff.

## Evidence record and gate decision

For a separately approved run, store a concise sanitized result containing:

- exact SDK/binary/version/full digest/mode/platform and launch settings;
- operation/request IDs and monotonic event watermarks;
- coordinator session/account/process/name/lane mapping;
- child `agent_id`/actual `task_id` where supplied/type/tool-use/parent
  mappings, transcript/store references, statuses, stop provenance, model/effort, definitions, and
  per-child hook/tool policy facts;
- process-tree and containing-group exclusion observations;
- accepted-send/query counts before/during/after swap, release, and restart;
- cross-profile child-store results, partial-start/retry outcomes, completed
  no-replay evidence, and refusal/uncertainty reasons; and
- the exact disposable configuration and elapsed bounded-stop/start times.

Do not record full transcripts or credentials. A passing run establishes only
the exact tested configuration and participant kinds. Missing evidence,
unexpected inference, uncorrelated child events, policy bypass, an unknown
detached effect, duplicate replay, or a manually bypassed hook fails the gate.
Live capability remains `UNVERIFIED` until a separately authorized and
reviewed result supports a narrower published claim.

## 2026-09-18 corrected evidence-harness disposition (documentation only)

This additive section records the disposition after the evidence-harness
semantic review. It is not a new probe run: Luna executed no probe, test,
runtime, network, account, or profile operation for this section, and no task
checkbox or acceptance gate is closed. The historical observations and their
limits above remain unchanged. In particular, a candidate arm being
executable in the harness is not evidence that the selected runtime supports
the lifecycle operation.

The corrected harness has bounded candidate dispatch for Gate 0 cases
`positive-orphan` and `terminal-cleared`. The former delegates to the
loopback runner's crash-owned-process-group/unfinished-record arm; the latter
delegates to the `stop_task` arm. Both verify the selected SDK/CLI identity and
retain `support_claim=false`. They are mechanical observation attempts, not
positive support paths. The checked-in event JSONL and source fixtures remain
extracted feasibility controls only; they are not selected-CLI output and are
not an authority for a runtime result.

### Current fact disposition

| Surface | What the harness can attempt | What is actually established now |
| --- | --- | --- |
| Gate 0 positive orphan | Seed an unfinished loopback record, end the owned source process group, and hold a target using the selected runtime. | No corrected runtime arm was executed in this lane. The selected CLI has no evidenced stream-JSON subtype or authoritative API for persisted-record load, restored-orphan admission, child-parent wake, or notification enqueue. Those facts are `UNKNOWN`; the arm is `unsupported`/`unverified` with no support claim. |
| Gate 0 terminal cleared | Exercise the bounded `stop_task` source control, then hold the target and assess worker/orphan clearing independently. | Historical `stop_task` runs observed receipts, stopped/task-terminal/tool/process facts, but also observed a new source `/v1/messages` request during source control. Therefore the corrected negative gate is `source-control-request-observed` and `control_request_free=false`; this is not a terminal-clear success. No independent selected-runtime emitter proves `worker_state_clear` or `orphan_state_clear`, so each remains `UNKNOWN`. |
| Busy parent | Identify the pending parent Agent continuation before control and correlate child/Bash activity. | The historical busy-parent artifact proves the pending-parent and pre-entry child/Bash observations. The blocked response was released with `response_completed=false`; that is not cancellation evidence. Response-write disposition, parent/session aggregation, or a later result cannot promote it to cancellation. Exact held parent load and restored-task wake remain `UNKNOWN`. |
| Coordinator interrupt | Attempt a turn-wide interrupt with one sticky loopback request-observation epoch. | The historical settled-parent candidate recorded native stop/tool/process facts and zero arrivals in its scoped epoch, but it was not a busy-parent, multiple-child, nested, completion-race, or in-flight-admission proof. The current corrected harness still lacks the authoritative lifecycle surfaces needed for those claims. The mode remains `unsupported`/`unverified` for production. |

The following distinctions are deliberate. A `control_response`, interrupt or
stop receipt, `task_started`/task notification, tool-terminal join, process
identity/exit, session UUID, or loopback `/v1/messages` route count is a real
mechanical observation when correlated in the report. None of those alone
proves exact parent loading, an orphan wake, durable state clearing, or
response cancellation. In particular, `launched && hold_complete` is not a
target-connect observation, and a zero uncalibrated wake counter is not a
target-no-wake observation. The corrected terminal assessment therefore keeps
`target_connect`, `target_no_wake`, `exact_parent_load`, `worker_state_clear`,
and `orphan_state_clear` independent and `UNKNOWN` unless their own
correlated surface is present.

### Missing selected-runtime event surface

No exact selected CLI stream-JSON emitter or authoritative state API has been
evidenced for the proposed labels `persisted-record-load`, `restored-orphans`,
`child-parent-wake`, `durable-worker-state-clear`, or the internal/source names
`restoredOrphans` and `enqueuePendingNotification`. The same applies to the
fixture/internal `running_background_tasks` and generic `durable_state_clear`
labels as proof of the independent worker and orphan facts. These names are
not protocol subtypes merely because they occur in extracted source or
synthetic JSONL. The corrected harness no longer treats a bare alias as an
observed control event; injected fixture events can validate parsing and
fail-closed classification only.

This is also why repeating a runtime arm cannot turn the aliases into
evidence. Repeating the same synthetic fixture repeats a parser/control-shape
test, not a selected-binary emission. Repeating the loopback arm can measure
bounded endpoint arrivals and process facts, but it cannot create the absent
CLI lifecycle event, correlate an internal durable record, or establish a
state-clear transition. A real supported stream-JSON emitter or authoritative
runtime state surface must first be identified and pinned; none is evidenced
by the artifacts recorded here. No repeated arm is therefore claimed as a
resolution of the positive-orphan or terminal-clear gap.

### Pinned identities and historical artifact references

The only selected-runtime identity evidenced by the historical runs is SDK
`claude-agent-sdk==0.2.153`, bundled CLI `2.1.273`, CLI SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`, and the
existing local image reference `py-bench:brett` with image ID
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`.
These pins describe the historical disposable environment; they do not grant
production access or imply that a corrected arm has run.

Previously recorded private artifacts remain historical evidence only:

- busy-parent report `openrepotools-busy-parent.MfKev7/report.json`,
  SHA-256 `bd463d8fc4f0daa189b1cc11341e1f5309358dd2395e795a4c8c78cb2ed696b0`;
- settled control-entry report
  `openrepotools-native-loopback-runtime.cyIjNi/report.json`, SHA-256
  `fd329c35d988ecf0574d25ae06c8f3b5882e0c669b42a1abbcfe88f169fa6dec`;
- its private log, SHA-256
  `aac8b025a0b350aec3bc561dbf263de4d0af9612509e31a92b1323b4b5607d85`;
- the initial Gate 0 baseline artifact
  `managed-gate0-baseline-20260918.json`, SHA-256
  `a6c3da53ae12280e546b9d651c1a991b30daf46ed28dfece66d4880f3d3f7598`.

The busy-parent report remains `verdict=inconclusive` and
`support_claim=false`; the control-entry report has the same disposition.
Sol's focused immutable-snapshot unit/fake slice reported 279 passed, one
unrelated SDK-rollover failure, and 1543 deselected; that result was not a
runtime arm and was captured before this semantic correction. The failure was
`_consumed_reservation_ids.append(...)` on a set in the SDK lane and is not
evidence for or against the lifecycle controls here. No corrected probe-test
result is asserted in this section.

### Safe candidate invocations for Sol (not executed here)

When Sol has the separately authorized isolated bench, these are the exact
bounded candidate invocations against the existing image reference. The
selected SDK interpreter must already be the pinned isolated interpreter; no
package install, image pull, credential, profile, or network access is part
of these commands. The Gate 0 wrapper creates the disposable child with
`network=none`, no host mounts, and bounded cleanup, and reserves each output
file as a new private `0600` artifact:

```sh
python3 tests/probes/managed_gate0.py \
  --sdk-python "$PROBE_SDK_PYTHON" \
  --image "py-bench:brett" \
  --case positive-orphan \
  --output "$PROBE_DIR/positive-orphan.json"

python3 tests/probes/managed_gate0.py \
  --sdk-python "$PROBE_SDK_PYTHON" \
  --image "py-bench:brett" \
  --case terminal-cleared \
  --output "$PROBE_DIR/terminal-cleared.json"
```

These commands are candidate no-auth/no-network validation attempts, not
acceptance commands: any output must preserve the unknown facts and
`support_claim=false`, including the terminal-cleared negative gate when the
source control request is observed. Their use cannot turn the missing event
surface into production capability.

### T030 alternative disposition

For Astra's review, the explicit T030 fallback is now documented: the
selected runtime's positive-orphan, terminal-cleared, busy-cancellation,
exact-parent-load, worker-clear, orphan-clear, and complete coordinator
roster surfaces are `unsupported`/`unverified` wherever the required
authoritative observation is absent. Thus T030 is complete only through its
explicit **unsupported/unverified alternative**. This closes T030's evidence
disposition requirement, not native/runtime/feature acceptance: no
selected-runtime support claim is made. Authenticated account/profile
validation remains **NOT RUN — UNVERIFIED**.
