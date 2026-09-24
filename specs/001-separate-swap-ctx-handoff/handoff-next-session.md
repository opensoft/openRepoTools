# Swap rebuild — implementation handoff

## Latest checkpoint — thirteenth Bite 4 INCONCLUSIVE; T050 offline correction approved

The user authorized exactly one thirteenth Bite 4 run; Sol reviewed and froze
the command. It exited 2 after about 20 seconds, INCONCLUSIVE, with positive
reason `effect-or-observer-uncertain`; the negative arm was not run and no
target container was created. Source stop/removal and target-state volume
creation occurred before source-report schema validation failed, before copy,
release, or target creation. The inner source exception was not retained. The
unbound `parent_uuid` reference in the legacy/source initializer is a
deterministic static cause candidate, not directly proven historical cause.
The inventory is zero labeled containers and two unattached labeled volumes
(one source-state, one target-state); no cleanup or replay of the thirteenth
run is authorized. The user has since authorized exactly one fourteenth full
diagnostic run, pending push, Sol's post-push preflight/command review, and the
required command seal. Do not run before all are complete; this authorization
does not include cleanup or deployment. Bite 5 remains pending and production
unsupported.

T050 is a future-only correction approved by Astra. It removes the unbound
initializer, adds allowlisted error-site metadata, privately persists and
validates the exact source report before further effects, and quarantines
malformed fallbacks with a fixed public reason. An otherwise-valid explicit
target-code reach remains FAIL; missing/unknown reach remains INCONCLUSIVE.
Sol's canonical focused gate passed 427 tests, 2,168 deselected, zero failures;
JUnit SHA-256 is
`f887c8d09ccfd49c1a59165b2cf59c4102d108d1655821382266e38267619633`. This
future-only gate does not revise the thirteenth run or itself grant runtime
authority; the separate user authorization is recorded above.
T049's default `strict-v1` behavior remains unchanged. Full details and sealed
hashes are in [`verification.md`](verification.md).

The full repository suite ran once with 2,560 passed, 28 failed, zero skipped,
five warnings, in 3,951.61 seconds. Ten stale loopback test fixtures from that
run have been fixed, and the expanded T049 gate passes. Fourteen native
context/restoration failures hit the unchanged unsupported controller gate.
In an isolated three-node rerun, the CLI unsafe-parent and daemon-route cases
passed; the CLI persistent-lifecycle case failed on an ownership conflict.
The shell aggregate was not rerun, and the full suite was not rerun after the
fixture fixes. Do not report this as a green full suite or as evidence that the
remaining failures are baseline or timing-only.

## Historical checkpoint before thirteenth run — twelfth-run evidence

The first twelve full Bite 4 runs produced no PASS. Runs one through six
were INCONCLUSIVE before release; runs seven, eight, eleven, and twelve reached
the startup-task gate and remained INCONCLUSIVE; runs nine and ten refused
before release because source terminal-task evidence was unavailable. T048's
bounded SDK-sidecar identity bridge and mismatch diagnostics passed Astra
architecture review and Sol's formal offline gate: 243 selected tests passed,
2,270 were deselected, with zero failures, errors, or skips. Frozen
probe/test/harness hashes are native probe
`cec4b4f5010e4e9c56c08492b1a12692689b8160ba0f213b779adc75e44819dc`, tests
`eb462ac654390785bc45fd0e84b0b1f675dc539c6ea89e62bc95c5e0db65c29b`, and
harness `bb5161ba852aaa7f83c314d171b3929dcbca07c106b8899ee514f085ee111a77`.

The separately authorized twelfth attempt ran exactly once and exited 2 with
sanitized status INCONCLUSIVE, reason `startup-task-event-observed`,
`observer_complete=true`, `release_candidate_ready=true`, and
`cleanup_complete=false`. Its T048 source seed was available. Exact copy and
pre-release custody passed; durable release, launch intent, target creation,
and final custody were observed. A complete stopped target
`system/task_notification` matched session/task, while optional agent/tool
identity remained unknown and the event UUID differed from the source parent.
The sticky gate correctly withheld the history query; no parent/child startup
messages were observed, and the negative arm did not run. Final custody
retained the saved edit and linked source-parent history prefix, but does not
establish whole target-tree immutability: the target parent JSONL grew from
52,825 to 55,372 bytes and `other_config_mutation_count=1`.

The twelfth sealed result digest is
`4289f073b7c8508633f13c829d0ed670c813f917480ff106bd0525d14ee24294`. Its
pre-cleanup inventory was 19 volumes (12 source-state, seven target-state),
five older stopped containers (four Bite 4 and one metadata diagnostic), zero
running containers, and no current target container. After that sealed result
was verified, the separately authorized cleanup completed: all 19 volumes and
five stopped containers in the exact allowlist are absent. The sealed bundle
and its 36-entry manifest remain unchanged; no evidence was deleted and no
prune or unrelated removal occurred. The private mode-0600 allowlist artifact
has SHA-256
`d6ea783b66a4bee326ee23b83d80a82797f2f633db19831b131b0ac4cd0a4d78`. The
twelfth authorization is consumed. At that historical checkpoint no
thirteenth attempt was authorized; the later one-run authorization and result
are recorded above. Bite 5 remains pending review; production remains
unsupported. Full hashes and the negative arm reporting caveat are in
[`verification.md`](verification.md).

### Twelfth full Bite 4 run — INCONCLUSIVE; one-run authorization consumed

The public report records schema `openrepotools-bite4-two-domain-report/v1`,
`bite5_decision=pending-review`, `production_disposition=unsupported`, and
`support_claim=false`. Source stop event 34 and target stop event 151 were
harness/engine enforced with exit 137 and `oom=false`; source removal was event
36. Copy verification was event 92 and exact pre-release custody was event
119. Durable release, launch intent, and target create were events 120, 121,
and 123. Target removal was event 153, final helper removal event 179, and
event 180 persisted the final-custody result.

The target produced one complete stopped task notification with matching
session/task and unknown optional agent/tool identity. Its event UUID differed
from the source parent, so the observation is terminal-correlation-only and
does not prove replay or that no new execution occurred. The gate recorded
`successful_result_seen=true` but `history_query_allowed=false`; no history
query or read was sent. Astra's review confirms the gate behaved as specified.
The negative arm's generic reason, `positive-release-candidate-not-established`,
is misleading because `release_candidate_ready=true`; its actual unmet
prerequisite was `cleanup_complete=false` while the INCONCLUSIVE run's resources
were preserved. The negative arm correctly remained not-run.

No loaded-history proof or Bite 3 OS witness/all-path restart fence exists, so
this is not a Bite 3 PASS or Bite 5 verdict. The authorization is consumed;
the resources listed above were the pre-cleanup inventory for this run. The
separately authorized post-run cleanup is recorded below.

### Post-run authorized cleanup — complete

On 2026-09-24, after verifying the sealed twelfth-run evidence, Sol High
executed the exact separately authorized cleanup. Its preflight covered 19
labeled diagnostic volumes and five stopped containers, with no running
containers or unrelated attachments. All 24 allowlisted resources were
confirmed absent afterward. The sealed bundle and 36-entry manifest are
unchanged. No prune, evidence deletion, or unrelated resource removal
occurred. The exact allowlist is retained only in a private mode-0600 artifact
with SHA-256
`d6ea783b66a4bee326ee23b83d80a82797f2f633db19831b131b0ac4cd0a4d78`.
Cleanup completion does not change the INCONCLUSIVE Bite 4 result or authorize
a thirteenth attempt. Bite 5 remains pending and production unsupported.

### Thirteenth full Bite 4 run — INCONCLUSIVE; one-run authorization consumed

The public report records `diagnostic_status=INCONCLUSIVE`,
`bite5_decision=pending-review`, `production_disposition=unsupported`, and
`support_claim=false`. The positive arm is INCONCLUSIVE with
`effect-or-observer-uncertain`, `observer_complete=false`,
`cleanup_complete=false`, and `release_candidate_ready=false`. The negative
arm is `not-run` with `positive-release-candidate-not-established`,
`positive-cleanup-incomplete`, and `positive-observer-incomplete`;
`target_container_created=false`. `explicit_release_selected=true` records
selection only; no release or target launch was reached.

The source was observed running after its phase and later stopped and removed.
The target-state volume was created; source-report schema validation then
failed before copy or release. The sealed artifacts contain no inner source
exception and no event indices. An unbound `parent_uuid` reference in the
legacy/source initializer is a deterministic static cause candidate, not a
directly proven exception. Quarantine counters are zero,
`volumes_removed=false`, and `leftovers.manual_review_required=true`. The
preserved inventory is zero labeled containers and two unattached labeled
volumes (one source-state, one target-state). At that thirteenth-run checkpoint,
no cleanup, retry, or fourteenth authorization was permitted.

Sealed manifest SHA-256:
`5815a42167d5a772131368264111f9cb124f726fe33e101dee318eb3f8bd9d23`.
Sanitized stdout:
`cd94d74854d88431c178b17b8893179e34b8821034e4570f02986051a86f374a`.
Private report:
`55d8311397fa473ee85612ea0e95c60ce6aa0caee074d2f360632964b6ab146e`.
Abort ledger:
`b898eabb9f181fdcbf8a0c00d11f36090417d9ad62059bc8a183072d8ba557a8`.
Runtime pins are SDK 0.2.153, CLI 2.1.273 SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`, and
image SHA-256
`a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094`.
Bite 5 remains pending and production unsupported.

## Historical checkpoint — 2026-09-23

All eleven full Bite 4 runs have produced no PASS. Runs one through six were
INCONCLUSIVE before release; the seventh, eighth, and eleventh reached the
startup-task gate and remained INCONCLUSIVE; runs nine and ten refused before
release because source terminal-task evidence was unavailable. T048's bounded
SDK-sidecar identity bridge and mismatch diagnostics passed Astra architecture
review and Sol's formal offline gate: 243 selected tests passed, 2,270 were
deselected, with zero failures, errors, or skips. Frozen probe/test/harness
hashes are native probe
`cec4b4f5010e4e9c56c08492b1a12692689b8160ba0f213b779adc75e44819dc`, tests
`eb462ac654390785bc45fd0e84b0b1f675dc539c6ea89e62bc95c5e0db65c29b`, and
harness `bb5161ba852aaa7f83c314d171b3929dcbca07c106b8899ee514f085ee111a77`.
The eleventh attempt was executed once under separate user authorization and
exited 2, INCONCLUSIVE with `startup-task-event-observed`; its authority is
consumed. Seventeen volumes (11 source-state, six target-state), five older
stopped containers, zero running containers, and zero current target
containers remain preserved. No cleanup, retry, or twelfth attempt is
authorized. Bite 5 remains undecided; production remains unsupported.

### Historical eleventh full Bite 4 run — INCONCLUSIVE; one-run authorization consumed

The T048 v3 source seed was available through the SDK-sidecar proof and
`release_candidate_ready=true`. The outer invocation exited 2 with
`startup-task-event-observed`. Source stop/removal was harness/engine enforced
(exit 137); exact copy, pre-release custody, and final custody were retained.
Durable release, launch-intent, and target-create events were recorded at
sequences 120, 121, and 123; final custody was event 180. The target harness
also stopped/removed with exit 137. The target produced one complete stopped
`task_notification` with matching session/task; optional agent/tool identity
remained unknown and the UUID differed. Under the unchanged sticky gate, the
history query was skipped. No parent/child startup messages were observed and
the negative arm did not run. This is not a Bite 3 PASS or proof that history
was loaded.

The sealed result digest is
`9403d9910279ec0c6f047f53dc4d1c672751e90bb63d637985803c8202f04e5f`. Private
bundle label: `openrepotools-bite4-eleventh-preflight.YKJSLl`. Artifact hashes,
formal T048 gate digests, and exact custody notes are in
[`verification.md`](verification.md). The preserved inventory is 17 volumes
(11 source-state, six target-state), the same five older stopped containers,
zero running and zero target containers. No cleanup, retry, or twelfth run
occurred or is authorized.

### Historical tenth full Bite 4 run — INCONCLUSIVE

The tenth invocation exited 2. Its positive result reason was
`source-native-task-terminal-seed-unavailable`, with detailed reason
`terminal-task-hook-evidence-incomplete`. Four lifecycle-v2 events were
complete: one started task with a tool-use ID and one hook callback rejected
as `hook-tool-use-id-mismatch`; zero hook callbacks were stored or joined.
Source stop/removal was harness/engine enforced with exit 137, not natural
graph shutdown. Exact copy, pre-release identity-linked history custody, and
final saved-edit/history-prefix custody were retained. No release or
target-launch ledger, target runtime container, or positive release candidate
was established; the negative arm did not run.

There are 15 preserved volumes (10 source-state, five target-state), the same
five older stopped containers, zero running, and no tenth-run container. No
cleanup occurred. Event 146 persists the final result with sealed digest
`addefcf9282109879c5fd1eaa74a199eb03949e8b81ed8c13b4728a837db8258`; full
artifact digests are in [`verification.md`](verification.md).

Astra's post-run interpretation is that rejecting the mismatched hook was
correct and fail-closed. The pinned SDK forwards an optional callback tool ID
but does not guarantee equality semantics with the selected task tool ID. The
retained summary lacks the rejected hook's event kind and digests, so it cannot
distinguish a different tool role, task, or association. This does not show a
CLI defect. Any future investigation should capture bounded rejected-hook
event kind/order and separate callback/input/current-task/session/tool
digests, then seek an authoritative structured bridge; do not relax exact
equality or infer joins from cardinality.

### Historical ninth full Bite 4 run — INCONCLUSIVE

The one authorized ninth attempt ran once and exited 2 with a sanitized report
whose support_claim is false. The positive arm reason was
source-native-task-terminal-seed-unavailable, with observer_complete=true,
release_candidate_ready=false, and cleanup_complete=false. The negative arm
was not run and a positive release candidate was not established.

Source stop and removal, exact copy, identity-linked pre-release parent-history
custody, and final custody of the copied volumes were observed. The source
parent exited and tracked fixtures were excluded, but source-container shutdown
was harness/engine enforced with exit 137; this was not natural graph shutdown
or production containment evidence. The source projection says the terminal
seed was unavailable but omits the detailed unavailable-reason envelope, so
the exact missing identity/event condition remains unknown. The target-state
volume was copied, but no release or target-launch ledger and no target runtime
container were created. Public event 146 records
final-custody-result-persisted with the sealed digest; the event ledger covers
events 1–145 before that final event.

The run added two preserved volumes. Current inventory is 13 total (nine
source-state and four target-state), five older stopped containers (four Bite 4
and one metadata diagnostic), zero running, and no ninth-run container. No
cleanup or retry occurred. The single-run authorization is consumed; no tenth
run or cleanup is authorized. Available-seed transfer, target fingerprint
validation/correlation/startup/history query, and the negative arm remain
unexercised. The T046 offline closure remains intact. Exact evidence hashes are
in [`verification.md`](verification.md).

### Historical eighth-run checkpoint

T036/T037 and the future-only T038 interactive-stdio correction passed Astra's
targeted reviews and Sol's focused offline gates. T041 also passed Astra review
and Sol's 144-test `two_domain` gate. The T043 sanitizer and T044 detached
startup-task snapshot corrections passed Astra's integrated review and Sol's
151-test focused offline gate. All eight full Bite 4 runs failed to produce a
PASS. Runs one through six were INCONCLUSIVE before release. The seventh
reached final custody, but its public report had a sanitizer false positive;
its private arm was INCONCLUSIVE on a startup task event.

The eighth run exited 2 with a sanitized INCONCLUSIVE report. It observed
source stop/exclusion, exact copy, pre-release history custody, durable
release, exact-parent target start/stop/removal, and final saved-edit/history
custody. Its target startup snapshot recorded one `system/task_notification`
with `stopped` status and matching session correlation. Task/agent identity
remained unknown, source terminal seed was unavailable, and identity was
unresolved; the snapshot was unknown/incomplete. The sticky gate correctly
skipped history query, and the negative arm did not run. No assistant/tool
activity, parent/child messages, or gateway routes were observed. This is not
PASS under Bite 3 and does not decide Bite 5.

The eighth run added two preserved volumes; there are now eleven engine
volumes (eight source-state and three target-state) and five older stopped
containers (four Bite 4 and one metadata diagnostic), with zero running and no
eighth-run container. No cleanup or ninth run is authorized. Bite 5 remains pending and
production unsupported. T043's sanitizer correction was exercised in the
eighth run: it masks only the resolver-validated `identities.image_id` leaf in
a copied scan projection while keeping the resolved ID and all other private
values checked, and the sanitized report passed packaging. The T044 target
snapshot recorded the unresolved startup task described above without changing
the sticky gate. Astra's integrated review passed; Sol's focused offline gate
passed 151 tests with zero failures/errors/skips in 9.749s. The runtime result
remains INCONCLUSIVE. Frozen hashes used for the eighth attempt:
harness `a3852a6969599c1b605edb60a371069d6de9f41317a9082cd69c0e65ab800c62`,
native probe `bf7032097ba264aa199e6f0555d4ab4412c85043b0b12e674a8a4461722d78e9`,
tests `c23f6a3d91aafc33dd056b67d89034363c7ba6ecea494389b519b6897fd698fd`.
The eighth run's result and artifact hashes are in `verification.md` and
`live-validation.md`. Its one-run authorization was consumed; no ninth run or
cleanup was authorized at that checkpoint.

T046 adds a future-only source-to-target native-task seed handoff. It carries
only a bounded sanitized terminal event and identity digests; binds the seed
to the source parent/invocation, phase digest, release/launch intents, and
target-spec fingerprint; and refuses missing/incomplete source identity
before release or target creation. The target verifies the full fingerprint
before any CLI subprocess and uses existing strict correlation without
changing the sticky startup gate. Astra architecture review passed. Sol's
focused `two_domain` offline gate passed 155 tests with zero failures, errors,
or skips in 5.715s. The ninth run exercised the unavailable-seed refusal but
did not exercise available-seed transfer or target fingerprint/correlation/
startup/history query. Frozen code/test hashes and offline artifact digests
are in `verification.md`.

### Historical T047 checkpoint — architecture and offline gate PASS; runtime INCONCLUSIVE

T047 is a future-only diagnostic repair to the unavailable-seed path. The v2
seed keeps `task_started_event`, terminal `task_notification`, and
`agent_proof` separate; it preserves the sanitized terminal observation,
keeps source-side correlation all unknown, and requires exact session/task and
strict start-before-terminal linkage. Agent proof is direct from the start
event or exact hook evidence by session/tool-use ID, with task ID checked when
present. Source hooks are enabled for the diagnostic; unresolved callbacks
join later only through those exact digests. Missing tool IDs, reused or
ambiguous task/agent binding, conflicting identities, malformed evidence, and
overflow remain unavailable. `task_updated.patch.status` is recorded, but
update-only evidence is not promoted. Target-side absent optional agent/tool
fields remain unknown, while present conflicts refuse correlation. The
sticky startup gate is unchanged. Bounded path-free reason/lifecycle/hook
diagnostics are retained in the private source projection and bound by the
source-phase digest.

Astra's final architecture review passed and Sol's canonical gate
`tests/run.sh --parallel-safe -k 'two_domain or native_task or native_hook or hook_ack or source_terminal_seed'`
passed 210 selected tests, 2,270 deselected, zero failures/errors/skips, in
13.02s. Luna's focused development selector passed 207 tests with 2,273
deselected. Frozen code hashes and private evidence digests are in
`verification.md`. The tenth runtime attempt exercised this repair but remained
INCONCLUSIVE before release/target creation because hook evidence was
incomplete. At that T047 checkpoint, the tenth authorization was consumed and
no eleventh attempt had yet been authorized. This is historical; the later
eleventh authorization is now consumed as recorded at the top of this handoff.
Bite 5 remains pending.

Current changes are uncommitted; preserve every inherited and current probe,
harness, test, metadata scanner/runner, and feature-record file. The user has
separately authorized commit and push; they are not performed by this
documentation update. Historical twelfth-run cleanup did not include the two
thirteenth-run volumes, which remain preserved; no cleanup is authorized.
Only PASS under Bite 3's evidence criteria permits public v1 lifecycle
implementation. No deployment or activation is authorized.

## Next-session action — pending fourteenth-run preflight

Start in this existing worktree and branch. Read this checkpoint together with
[`contracts/source-only-diagnostic.md`](contracts/source-only-diagnostic.md),
[`runbook.md`](runbook.md), [`live-validation.md`](live-validation.md), and
[`verification.md`](verification.md). T050's implementation and formal gate
are frozen; the thirteenth run remains INCONCLUSIVE and its authorization is
consumed. A separate user authorization covers exactly one fourteenth full
diagnostic run after push and pending Sol preflight/command review. Do not
execute it before that review. This authorization does not permit cleanup or
deployment; the two unattached thirteenth-run volumes remain preserved, and
the twelfth run's separate cleanup does not cover them. Preserve the sealed
evidence, artifacts, and uncommitted/untracked files. Bite 5 remains pending
required evidence.

Do not infer Bite 4 completion, production containment, or a Bite 5 verdict
from T050's offline gate or either INCONCLUSIVE runtime. Any proposed
protocol or gate change requires a separate review and authorization. Commit
and push have separate user authorization; this update does not perform them.
Do not deploy or activate public v1 lifecycle behavior.

Maintain the named roles: Astra is architecture lead, Sol High is runtime and
offline-gate executor, and Luna Max is implementation writer. Preserve all
uncommitted and untracked files. Do not commit, push, deploy, activate public
v1 lifecycle behavior, or mark Bite 5 passed, failed, or inconclusive without
the required evidence and an explicit decision record.

## Historical next-session start — 2026-09-22 checkpoint

Resume in the existing feature worktree on branch
`001-separate-swap-ctx-handoff`. The current work is intentionally
uncommitted: preserve every inherited and current modified file, the two-domain
diagnostic design, operator runbook, candidate harness and focused tests, plus the pre-existing
untracked `.agents/`, `.codex/`, and `.specify/` bootstrap directories. Do not
reset, stash, clean, or commit them without a separate landing instruction.

Current checkpoint: **bites 1–3 are complete; all four full Bite 4 attempts
are INCONCLUSIVE; the first three stopped before selected source startup and
the fourth stopped after container start but before any container exec or SDK;
T033's future-only volume observer
and T034 mount-builder correction passed architecture review and focused offline
tests; the narrow T034 create-only smoke passed; four source-state volumes
and two source containers (one Created, one Exited 137) remain preserved; the
fourth authorization is consumed with no fifth runtime authorized; T035 passed
targeted architecture review and its focused offline gate but is not runtime
verified; Bite 5 is pending with no verdict**. The default-off
`--observe-native-hooks` diagnostic records bounded SDK child-hook facts and
handles pinned callback ACKs; it does not enable production swap, prove
containment, prove history loading, or claim child restoration.

The first Bite 4 invocation aborted because the label-filtered volume stream
did not observe a create event. Read-only diagnosis found the matching event
without run/role attributes; that volume remains preserved. The separate
user-authorized follow-up used T033's corrected volume observer and progressed
past volume creation, but Docker source-container creation failed with exit
125. The exact daemon stderr was not retained, so the cause remains
unconfirmed. Sol's read-only diagnosis identifies explicit `rw` in the
writable volume `--mount` as a moderate-to-high-confidence command-builder
suspect; this is an inference, not observed daemon output. Astra agrees on a
future-only offline correction and private bounded stderr capture.

The second report is `INCONCLUSIVE`, `support_claim=false`, production
unsupported; after those first two attempts, the positive arm was inconclusive with
`release_candidate_ready=false`, `observer_complete=false`, and
`cleanup_complete=false`. The negative arm was NOT RUN. Neither attempt started
a source SDK/runtime or reached history, release, target, or startup. There are
zero run-labelled containers; two `source-state` volumes are preserved, with
no cleanup or retry. The separate run's artifact hashes are in
`live-validation.md`; frozen harness/helper/test hashes are unchanged and the
39-test offline result for T033 is in `verification.md`.

Luna authored the uncommitted future-only correction: writable volume mounts
omit the access token, read-only mounts use readonly, and Docker failure
stderr is retained only in the private mode-0600 abort ledger. Astra review
passed; Sol's focused offline gate passed 41 tests (2,293 deselected in 9.09s)
after one redundant assertion was corrected. Astra's stated limits: retained
stderr is capped at 4,096 bytes, subprocess capture itself is unbounded, and
timeout/pre-arm failures do not use this ledger path. This correction is
offline-only and does not establish the cause of exit 125 or runtime behavior.
The separate user-authorized T034 Docker-create smoke then passed narrowly:
one fresh labelled container was Created but not Running, and inspect reported
the writable volume RW=true. Sol removed only the smoke-owned container and
volume and verified absence; both earlier source-state volumes remained
untouched. The smoke used the frozen builder hash recorded in verification.md.
It confirms only Docker create and mount semantics. It does not confirm the
former exit-125 cause, run the SDK/source, or complete Bite 4. The future-only
T035 correction recognizes Docker's exact unset-time
sentinel only alongside Created/Running=false/Pid=0, accepts configured tmpfs
before start only when active Mounts are absent, and requires active tmpfs
Mounts after start before any SDK/helper exec. Quarantine preserves a
corroborated never-started Created container without requiring a die event;
start-attempt or event evidence keeps the outcome uncertain. Focused offline
regressions cover exact timestamps, missing/null/empty/malformed alternatives,
tmpfs validation, post-start revalidation, and quarantine boundaries. Astra's
targeted review passed; Sol's canonical selector
`tests/run.sh --parallel-safe -k two_domain` passed 59 tests (2,293 deselected
in 6.74s). Frozen hashes and private output digests are in `verification.md`.
This remains offline-only; no runtime or cleanup was authorized by T035. A
later separate fourth attempt is recorded in `runbook.md` and
`live-validation.md`: it is INCONCLUSIVE and its authorization is consumed.
Later fifth-attempt and sixth-authorization records are in the latest
checkpoint above. The fifth run is INCONCLUSIVE and five volumes/three stopped
containers remain preserved. The sixth run is authorized, preflighted, and
shell-reviewed but awaits root GO. Preserve all prior resources; no cleanup is
authorized. Bite 5 remains pending with no verdict. Production activation and
deployment are not authorized.

### Fourth-run root cause and T036/T037 closure

T035 fixed the Docker representation for a corroborated never-started
`Created` container only. The running-state validator still requires tmpfs
destinations in top-level `Mounts` at
`tests/probes/managed_native_loopback.py:3538-3544`. The fourth run showed
`/tmp` and `/opt/loopback` in `HostConfig.Tmpfs` but not in `Mounts`, and
refused before any container `exec`. This means active tmpfs presence is
unproven, not absent. Docker CLI issue
[#3974](https://github.com/docker/cli/issues/3974) documents the separate
`HostConfig.Tmpfs` and top-level `Mounts` representations; the
[Linux proc mountinfo documentation](https://www.kernel.org/doc/html/v6.9/filesystems/proc.html#proc-pid-mountinfo-information-about-mounts)
describes a process's actual mount namespace and options. The same check serves
source, helper, and target starts, although only source was reached in this
run.

T036 now adds trusted, bounded `/proc/self/mountinfo` witnesses for source,
helpers, and target, bound by the external observer to exact container/image/
run/start identity and engine events, with a second fresh witness before
SDK/helper handoff. T037 preserves volumes on normal `fail` and `inconclusive`
returns. Both passed Astra review and Sol's 110-test focused offline gate;
details and hashes are in `tasks.md` and `verification.md`. The fifth run is
INCONCLUSIVE and the sixth is authorized but not started. Source SDK/history/
custody/release/target remain unobserved; startup/history concerns are
conditional, and the Bite 3 producer remains absent. Preserve all five volumes
and three stopped containers; Bite 5 remains pending and production
unsupported.

Bite 3 planning is recorded in
[`contracts/stop-then-resume.md`](contracts/stop-then-resume.md), with a concise
trace in `tasks.md` and `verification.md`. It binds the original runner PGID,
complete source roster, operation and invocation IDs, owner/lineage/runner/
daemon incarnations, launch-to-exclusion membership/escape coverage, and a
durable restart-deny fence enforced by every source recreation path. The
current lane-owning daemon must join fresh monotonic observations to a supported
OS-domain witness. Static inspection found no producer that proves this today;
production v1 therefore refuses at preflight. The loopback container remains
diagnostic only because source, target, and observer share it, history is
temporary, cleanup removes it, and isolation validation omits restart policy.

Astra reviewed and passed the Bite 3 architecture definition and the revised
Bite 4 two-domain diagnostic design. The [five-bite runbook](runbook.md)
records the exact sequence in
[`contracts/source-only-diagnostic.md`](contracts/source-only-diagnostic.md).
Bite 4 requires a source container that is stopped and removed before target
creation, read-only source history custody, an exact-byte target-state copy,
durable explicit release, and one exact-parent target launch in a separate
container. The design also specifies an independent unknown-effect refusal
arm, a persistent fixture workspace, atomic/fsync-backed host intents, and
read-only final target custody after writer exclusion. The one follow-up used the frozen T033 two-domain harness candidate; the
existing loopback probe behavior and validator remained unchanged. The 26-test
result was an earlier candidate. Astra passed a targeted architecture review
of T033; Sol's selector `tests/run.sh --parallel-safe -k two_domain` passed 39
tests (2,293 deselected in 9.47s). Frozen T033 hashes are harness
`1aa5f6f35beea569aa6c4f206cb7dcd08f9ee9d4cdea1bee5bc268ef34cd06b6`, helper
`4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695`, and
test `5f5869655cc046674dbd697e3f816fd28ea66e38c0f4a0203225d1695d5e2bca`.
JUnit SHA-256 is
`91b1b34dc62cf8e34035eea99b6bbdb37b3675518f1585fa469f220be580c6ba`; log
SHA-256 is `b62a03373d1fd2950579083ab6275d8b720143e8b7d5f4f9495fa5dcd1ec467e`.
Private evidence is in Sol's restricted artifact store (path kept private).
This is offline verification only, not Bite 4 runtime acceptance.
Sol's read-only runtime preflight passed for SDK 0.2.153, CLI 2.1.273 (digest
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`), and
local image `py-bench:brett` (immutable ID
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`).
The private artifact parents and machine-specific paths remain in Sol's
restricted record. The first run preserved one `source-state` volume and
created no run-labelled container; its matching Docker volume event lacked the
run/role attributes used by the then-filtered observer. T033's future-only
observer correction was architecture-reviewed and offline-verified. The one
later-authorized run used that correction, observed source volume creation,
then failed Docker source-container creation with exit 125. The daemon stderr
was not retained; an explicit writable-mount `rw` token is only a suspected
cause. It preserved a second source-state volume; total preserved volumes are
three, and the third attempt left one run-labelled Created source container.
None of the three attempts reached source SDK/runtime, history, release, target,
or negative arm; no cleanup or retry occurred. The report is INCONCLUSIVE, not a Bite 5 verdict. At that checkpoint the user
grant was consumed and no third run was authorized; a later user grant now
authorized one third full attempt, now completed with an INCONCLUSIVE result as
recorded in runbook.md. That authorization is consumed; no fourth runtime or
cleanup is authorized. Luna's later offline mount
builder/stderr-capture candidate is uncommitted; Astra review and Sol's 41-test
offline gate passed as recorded in `verification.md`. Exact runtime evidence is
in `live-validation.md`.

The current production source-evidence producer is still absent. Container
stop, history custody, and fixture restart settings do not prove Bite 3's
complete OS-domain membership/escape coverage or all-path restart fence. Keep
production preflight fail-closed regardless of a diagnostic-only observation.
Native unenroll and offline controller/recovery work may proceed independently,
but must not be mixed into this diagnostic slice.

Role continuity: Astra reviews architecture/correlation, Sol High is the sole
test/runtime executor, and Luna Max is the implementation writer. Keep edits
limited to the selected task and use `tests/run.sh` for offline tests; no live
account, credentials, installation, deployment, or production activation.

## Bite 1 evidence map — 2026-09-22

This is a historical repository implementation checkpoint, not a formal lane
handoff. Inspection covered HEAD `79f587a`, installed SDK `0.2.153` / CLI
`2.1.273`, and static source only. The prior 137-test result was historical
and was not rerun.

| Evidence producer | Status | Limit | Relative source / functions |
| --- | --- | --- | --- |
| Installed SDK `types.py`: `SubagentStartHookInput(agent_id, agent_type)`, `SubagentStopHookInput(agent_id, agent_type, agent_transcript_path)`, and `BaseHookInput.session_id` | Definitions exist; actual current-run callback linkage is unmeasured. | Types do not establish that a callback belongs to this run. | [probe initialization](../../tests/probes/managed_native_loopback.py) `initialize_frame`; installed `types.py` |
| Installed `_internal/sessions.py`: `list_subagents` scans names only (candidate); `get_subagent_messages` reads bodies and metadata, with `_parent_ids_from_agent_metadata` linking top-level `toolUseId` and `parentAgentId` | Metadata linkage is the bounded candidate path. | The body-reading helper is not an approved diagnostic shortcut; reports must never contain raw bodies, paths, or IDs. | [bounded discovery](../../tests/probes/managed_native_loopback.py) `_discover_history_paths`, `_history_sidecar_link`; installed `sessions.py` |
| At bite 1, probe `initialize_frame` sent `hooks=None`; production [guard-hook registration](../../lane_managed_sdk.py#L6381) already used `_build_guard_hooks` | Production hook registration existed; probe control wiring was absent. | This was resolved by bite 2's explicit opt-in hook registration and callback routing; `observe_frame` still did not provide an agent ID. | [probe frame path](../../tests/probes/managed_native_loopback.py) `initialize_frame`, `observe_frame`; [production](../../lane_managed_sdk.py) `_build_guard_hooks` |
| Production [runner](../../lane_managed_sdk.py#L10272) `popen_runner` uses `start_new_session=True`; [_RunnerConnection](../../lane_managed_sdk.py#L11165) shutdown checks quiescence and group liveness | TERM/KILL is limited to the owned process group. | This does not prove detached escape exclusion or external restart fencing. | [runner lifecycle](../../lane_managed_sdk.py) `popen_runner`, `_RunnerConnection.close` |
| Probe [cleanup](../../tests/probes/managed_native_loopback.py#L4083) `crash_owned_process_group` and captured fixture process checks | Prior evidence is harness-enforced parent exit and tracked-fixture-only. | It is not complete containment proof or loaded-context proof. | [fixture cleanup](../../tests/probes/managed_native_loopback.py) `crash_owned_process_group` |

Historical next-bite acceptance was diagnostic only: Luna added bounded
pinned-SDK hooks, response routing, and sanitized current-run correlations;
tests cover
registration, one ACK, unknown callbacks, malformed frames, reused IDs, stale
or conflicting joins, missing sidecars, filename-only non-promotion, and
privacy caps. Legacy behavior remains unchanged, with `support_claim=false`
and the sticky startup guard unchanged. Sol runs only the frozen focused probe
tests through `tests/run.sh` (no runtime or full suite), and Astra reviews the
schema and correlation. Stop and checkpoint after offline tests. Hook
completion is not effect safety. Bite 3 containment still needs explicit
domain/restart owners and a producer; unsupported conditions fail before
source disruption. No actual profile tests or activation are implied.

## Bite 2 checkpoint — 2026-09-22

Code is frozen after the explicit opt-in `--observe-native-hooks` diagnostic
slice: hooks default off; ACKs are bounded/once-only; malformed, conflicting,
stale, and reused joins fail closed; partial hook facts stay separate from
task-terminal/effect evidence; the startup guard, `support_claim=false`, and
no-history-attribution invariant remain unchanged. Sol's red snapshot had 8
new failures and 137 passed (2,140 deselected); the frozen green snapshot had
153 passed (2,140 deselected, 9.22s). The approved parallel-safe exception
was used because six unrelated pytest processes blocked serialized entry; this
is diagnostic evidence, not the full release gate. Probe SHA-256
`b02ca7ec99f4cfca5aee44e31ac74739d7cffb12ee5f4c8cfb650968f5884a35`, test
SHA-256 `bc1de523aabd0bf4ecad08ebd3c2329481778d8e03cdf8ad97499a4bd48ad763`,
JUnit `e7e2cf93fb07cbfab408ab469cc9944fe1aa07a200dcff54320ef4b854888667`,
manifest `f1541fb387325dc15ffabf11f46d9babc7f958bdd98bebf79d6ac83bf0e22395`,
private artifact basename `openrepotools-sol-bite2-green.Fn1pT3`. No runtime
test, production change, account activation, commit, or push occurred.
Evidence is limited to sanitized local hook correlation; the hook-to-history
sidecar bridge and real-runtime observation remain unverified, with no loaded-
context claim. Bite 3 must define owned containment/restart domain proof and
explicit refusal; no automatic experiment is authorized.

## Current September 22 direction

The approved [stop-then-resume-v1 decision](../../openspec/changes/separate-swap-ctx-handoff/stop-then-resume-decision.md)
and [contract](contracts/stop-then-resume.md) supersede the strict-only scheduling
below. Work stays in this feature/worktree with Astra architecture, Sol High
sole test execution, and Luna Max implementation. Implement the bounded v1
experiment before broad public lifecycle changes; target creation must happen
only after explicit release. Preserve strict-mode evidence and old records.
The independent native unenroll ownership-conflict fix remains in scope.
Current results and concrete blockers belong in `verification.md` and
`live-validation.md`; no installation or live canary is implied.

V1 checkpoint: its probe and regression tests are implemented. The frozen
candidate passed 113 focused tests, then ran explicit-release, unknown-effect
and withheld-release arms against SDK 0.2.153 / CLI 2.1.273. Release ordering,
saved-edit preservation and refusals were observed. A startup task event blocked
the extra history query; exact parent history and native child recovery remain
unproven. Parent termination was harness-enforced, not natural graph shutdown.
Use the final hashes and scope in `verification.md`; the public v1 lifecycle,
unenroll correction, broad regression gates and installation remain undone.
Do not remove the task-event guard or revive strict held-load requirements to
make this result look successful. Correlate the event/history and establish
the supported source containment domain before public integration.

Follow-up checkpoint: the startup-event/history diagnostic now passes **137
focused tests** and has one new isolated release run. Startup reported a stopped
task matching source session/task, but omitted the source's tool-use identity;
agent identity remains absent. Parent and candidate-child original file prefixes
were preserved. Candidate child attribution, exact runtime loading and complete
source containment remain unproven, and the query guard stayed closed. See the
final hashes and durable `openrepotools-sol-t003-t004-sidecar.e63Nfv` evidence in
`verification.md` and `live-validation.md`. No more diagnostic helper work is
needed merely to repeat this observation: next establish authoritative native
identity/history joins and post-release reconciliation, with the source-domain
proof still required. Public v1 and activation remain blocked.

## 2026-09-21 takeover

Published checkpoint: `5e940f00ec4b1d82dc9be0510b94b881316db631` on
`origin/001-separate-swap-ctx-handoff`. A subsequent T012 fixture correction
publishes the supervisor runtime identity before simulated owner takeover;
the five fence cases plus native-swap integration now report **19 passed**.
See `verification.md` for frozen artifacts and limits. T012 remains open.
The next unblocked diagnostic slice is the 12 native-worker observation
integration failures (watermark and source-operation binding); native ctx
still needs the contract/emitter work below. Keep the broader 34-failure run
as historical evidence, not a count recomputed from this focused success.

The user authorized continuation in the existing feature worktree. See the
[takeover record](../../openspec/changes/separate-swap-ctx-handoff/takeover-2026-09-21.md)
for preservation evidence, current role ownership, the refused workspace-log
publication, and proposed sibling integration order. The September 18 agent
assignments and diagnostic counts below are historical, not current claims
or evidence that those agents are still writing. Current test results belong
in `verification.md`; runtime support remains unverified.

Current continuation order (supersedes the older assignments below):

1. Use the September 21 frozen managed diagnostic in `verification.md` as the
   failure census; do not add together counts from distinct overlays. The
   takeover's production fixes preserve original hashed source archives and
   accept either child-start event order while retaining admission authority.
2. Resolve the ctx-specific pre-shutdown worker-clear evidence contract and
   establish an authoritative runtime emitter before implementing native ctx.
   The exploratory draft was preserved privately and removed from the candidate;
   positive ctx/restoration tests remain required. Do not substitute swap proof
   or post-shutdown adoption proof for this missing observation.
3. Resolve remaining managed and legacy failures, then run T027/T028/T029 from
   one frozen source using the serialized wrapper. The user's isolated-mode
   authorization covers diagnostics only, not release acceptance.
4. Have the workspace owner resolve the unrelated workspace merge before
   retrying the sanctioned takeover-log publication. No hand-written registry
   or workspace-config repair is authorized.

No task closure, production capability, installation, or merge is claimed.
Commit/push authorization covers the published checkpoints above, not release.
The preserved September 18 instructions below
describe their historical snapshot, not current writer assignments.

## Preserved 2026-09-18 checkpoint

Date: 2026-09-18. Active implementation checkpoint; not paused.
This is a repository implementation checkpoint, not a lane binding or a
replacement for the workspace's formal lane-handoff record.

## Resume here

Continue in branch `001-separate-swap-ctx-handoff`, in the sibling worktree
`../openRepoTools-worktrees/001-separate-swap-ctx-handoff` relative to the main
checkout. Do not implement in the main checkout. The worktree contains extensive
inherited modified and untracked files: preserve all of them. No commit, push,
reset, stash, install, or additional test run was performed for this wrap-up.

Read [plan.md](plan.md), [tasks.md](tasks.md),
[verification.md](verification.md), [live-validation.md](live-validation.md),
and the active OpenSpec change `separate-swap-ctx-handoff` before resuming.
The latest counts below supersede the earlier correction snapshot at the top
of verification.md; older results remain historical evidence, not waivers.
The checkpoint is not an authorization to claim runtime support or final
acceptance. Keep the worktree's inherited dirty state intact.

Current bounded ownership is active: root coordinates the implementation;
Astra is architecture lead and read-only contract reviewer; Sol High is the
orchestration/evidence and test executor; Luna Max is the implementation
writer for the defined Speckit tasks and contract/handoff documentation.
Additional bounded Luna roles are `Luna_children` for pure-module child
observation/restart-slot contract consistency and `Luna_packaging` for
packaging/help/legacy-alias assertion wording. These are documentation and
pure-module coordination roles only; they do not claim production capability,
test completion, or task closure.
Count live writers before assigning overlapping source or test edits, and do
not infer that an agent has stopped from an old pause note.

## Overall position

Implementation and contract work is substantial, but integration validation
is incomplete. Task closure is **8/32 Speckit tasks** (the snapshot-scoped
offline closures T005, T006, T007, T008, T022, T025, T026, and T030).
Governance closure remains separately tracked; no additional governance
approval is claimed here. These are closure counts, not an estimate of
engineering percentage complete. No native/runtime acceptance checkbox was
closed by this checkpoint.

The three current tracks are:

1. Busy-parent runtime evidence: bounded probe and unit tests complete;
   production support remains inconclusive.
2. Durable held-target adoption: transaction and crash-recovery implementation
   present; both adoption test modules pass. No production evidence provider
   is wired and no runtime adoption/release is enabled.
3. Prior controller/daemon regression migration: in progress. The retained
   prior focused run had 12 failures; consult `verification.md` for the
   current T028 and six-stage diagnostics. Final combined managed validation
   remains outstanding.

The latest active evidence is a clean **65-pass controller consumer/history
slice**, while the SDK child/no-send gate remains **229 passed/3 failed** and
the six-stage fixture-10 gate remains **26 passed/7 failed**. These are
diagnostic overlays, not acceptance or new task closures; the child fixes are
approved for rerun and the six-stage native-key/legacy-collector fixes remain
active. The new native-swap integrity path was not included, and authenticated
account validation remains not run. See `verification.md` for artifact paths,
full hashes, and the invalidated partial checkpoints.

## Changes already in the worktree

- `tests/probes/managed_native_loopback.py` and
  `tests/test_lane_managed_loopback_probe.py`: opt-in
  `--busy-parent-before-control`, exact Agent request barrier, sticky request
  epoch through target hold, precise completion attribution, bounded cleanup.
- `lane_managed_state.py`, `lane_managed_controller.py`,
  `tests/test_lane_managed_adoption_transaction.py`, and
  `tests/test_lane_managed_target_adoption.py`: bounded schema-2
  `native-adoptions.json` ledger, immutable bindings, durable phases
  prepared → claim-cas-pending → claim-transferred → controller-committed,
  exact claim CAS, and crash recovery without replaying uncertain CAS/runtime
  actions. Controller metadata stores a compact reference. Target is an
  ownership descriptor only; source history stays fenced and intact.
- Internal `_native_adoption_evidence_provider(binding)` constructor seam:
  absent by default, exact binding plus digest/reference and five literal-true
  proofs required. Never accept this provider through a request or probe.
- Controller `recover()` permits empty participant evidence only for validated
  unenroll mode and reconciles the trusted claim index; other modes stay strict.
- `_safe_runner_projection` accepts the exact SDK `RunnerSpec` type and omits
  17 non-durable slots only at canonical type-preserving defaults. Raw mapping
  environment/settings remain forbidden, including empty/null values;
  subclasses, lookalikes and non-default runtime controls get no exemption.
  Validated `supported_models` is configuration, not capability evidence.
- Swap-only reserved-to-written promotion requires the exact written UUID and
  exactly one trusted holder with profile/workspace/process-group ownership.
  Revalidates the resume spec before persistence/open. Missing, ambiguous or
  foreign holders and explicit fresh fallback refuse.
- Controller/daemon fixtures migrated toward coordinator-only native startup,
  real ownership claims, intent-before-open, explicit dispatch and no uncertain
  replay. Controller release does NOT dispatch inline: the public daemon
  release route owns one bounded pump tick.
- Added `tests/test_lane_managed_runner_projection.py` and
  `tests/test_lane_managed_reserved_transition.py`.
- Updated plan, data model, OpenSpec design and contracts, including
  [busy-parent-probe](contracts/busy-parent-probe.md),
  [native-adoption-transaction](contracts/native-adoption-transaction.md),
  [managed-control](contracts/managed-control.md), and
  [transcript-preflight](contracts/transcript-preflight.md).

## Retained test evidence from the prior checkpoint

Artifacts below are private temporary directories under the `py-bench`
container's temporary root; availability is not durable. Preserve hashes and
do not silently replace an old result with a new one.

The current T028 rerun and six-stage diagnostic are recorded in
[verification.md](verification.md); the table below is retained historical
evidence and is not the current acceptance result.

| Run | Result | Artifact | JUnit SHA-256 |
| --- | --- | --- | --- |
| Controller, daemon, target-adoption, adoption-transaction, reserved-transition | 257 passed, 12 failed, 1449 deselected | `openrepotools-five-module-focus.v4Yg5s/focused.xml` | `715dcbb1576e1417c00d6a484de24e49d58f39eaabf499180a9e8947cbebf467` |
| Runner projection | 45 passed, 1718 deselected | `openrepotools-runner-projection.5EdUFr/` | `dceed96eb3d6f1923d14abc69e96faa4216b8e0fa44315d156adace59af125dc` |
| Corrected probe units | 80 passed, 1629 deselected | `openrepotools-probe-unit-rerun.czlgLB/` | `0370573721966caa9a69e76c0a153196ffd1a3e772049d92ade8e53fca38b046` |

Selected manifests were unchanged across these runs. Both adoption modules
passed in the focused run. Do not add counts from different snapshots into a
single claimed green suite. Latest combined managed validation and final
strict OpenSpec validation are outstanding.

## Exact remaining failures and starting diagnoses

### Five reserved-transition tests — clear fixture defect

`_reserved_roster()` returns `_swap_roster(...)` directly, whose third return
value is a Participant, not the runtime. New tests unpack it as the runtime
and fail on `.opened` or `.calls`. Return `(controller, store, runtime)` using
the helper's locally constructed runtime, without changing the base helper.

- `test_swap_promotes_written_reserved_target_before_persist_and_open`
- `test_explicit_fresh_against_written_history_refuses_before_runtime`
- `test_written_fresh_without_exact_holder_refuses_before_metadata_mutation`
- `test_written_fresh_with_ambiguous_holder_refuses_before_runtime`
- `test_written_fresh_with_foreign_holder_refuses_before_runtime`

### Two controller tests — inspect contracts before changing assertions

- `test_recover_open_adopts_target_runner_spec_and_persists_profile_evidence`:
  actual phase `starting`, expected `ready-held`. This is an older mixed-roster
  recovery test with worker-b still pending; an overbroad expectation edit is
  suspected. Preserve accepted-open/no-replay assertions.
- `test_start_prevalidates_fixed_roster_and_records_ready_held_without_dispatch`:
  missing `intent["spec"]["fingerprint"]["lineage_context"]`. The prepared
  readiness spec and persisted launch-intent spec may differ by stage. Decide
  whether the binding is genuinely missing or the assertion targets the wrong
  representation; keep intent-before-open and identity checks.

### Five daemon tests — likely shared dispatch identity issue, not yet proven

- `test_real_controller_coordinator_busy_then_idle_dispatches_once_after_release`:
  message is `queued`, expected `fenced`, after explicit release and submit.
  Check released-state semantics; retain busy-no-send and idle-exactly-once.
- `test_real_controller_uncertain_dispatch_is_not_replayed_automatically`:
  `stale-generation` arrives before expected `uncertain-effect`.
- `test_real_controller_stale_generation_after_await_fence_blocks_send`:
  timeout waiting for resolver barrier.
- `test_real_controller_dispatch_releases_store_lock_before_runtime_await`:
  timeout waiting for send barrier.
- `test_public_cli_socket_uses_real_controller_for_held_release_and_one_ack`:
  release succeeds but no coordinator delivery before explicit pump.

Investigate the latter four together: `_native_start_body` uses incarnation
`daemon-native-runner`, while the fake runtime may expose `runner-coordinator`.
This is a hypothesis, not a diagnosed production bug. Inspect the early task
exception/pump diagnostics before waiting on barriers. Do not lengthen timeouts,
weaken stale-generation checks, change expected errors without reaching send,
or add inline dispatch to controller release.

## Busy-parent runtime evidence and limits

Exactly one corrected runtime run used SDK **0.2.153**, bundled CLI **2.1.273**,
with `--control-mode interrupt --busy-parent-before-control --release-target`.
Executable SHA-256:
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`.
Private report `openrepotools-busy-parent.MfKev7/report.json`, SHA-256:
`bd463d8fc4f0daa189b1cc11341e1f5309358dd2395e795a4c8c78cb2ed696b0`.

The probe ran with no network, no host mounts, no real credentials, and a
scripted loopback. Sandbox removal succeeded. It observed the exact pending
parent Agent continuation request, child/Bash liveness immediately before
entry (not atomically at entry), zero new requests through target hold,
interrupt/terminal/process-exit facts, and no forced cleanup. A post-release
request carried source and Agent history with the same observed session UUID.

It did NOT prove blocked-response cancellation, exact parent load while held,
completed-source continuity, child-header/task correlation, worker-state clear,
or orphan clear. Positive orphan handling was not exercised; the inspected CCR
path needs authentication. `eventual_continuity_observed=false`,
`continuity_scope=eventual-history-only`, `support_claim=false`, verdict
`inconclusive`. Do not invent flags, edit transcripts or fabricate evidence.
No repeat probe is needed merely for fixture corrections.

## Historical executor mapping — superseded by active ownership above

The role names remain authoritative, but the individual executor mapping
below belongs to the earlier checkpoint and must not be treated as a current
assignment. Use the active ownership block above and coordinate before any
overlapping edit. Use Codex-platform models only, following the existing
multi-model protocol.

- Sol / Erdos (`01a0b4d0-1fa7-78d0-be07-2cadff50ab76`): sole test executor,
  frozen manifests, evidence documentation.
- Newton (`01a0b4d0-2008-7e41-8bb8-1257df0631fb`): controller production and
  reserved-transition tests.
- James (`01a0b4f2-6e7e-7162-bcc7-36070fae58e9`): controller test corrections.
- Locke (`01a0b4d0-2066-75b0-bfff-64e325beca72`): daemon tests; coordinate any
  real production fix with Newton, never concurrent writers on one file.
- Jason (`01a0b4d1-5929-77c1-9396-97b8a3f359fc`): state/projection tests,
  available for independent bounded verification.

Fix the three independent failure groups in parallel, then freeze all selected
dependencies and let Sol run the canonical wrapper inside `py-bench`:

```sh
tests/run.sh --parallel-safe -k 'test_lane_managed_controller or test_lane_managed_daemon or test_lane_managed_target_adoption or test_lane_managed_adoption_transaction or test_lane_managed_reserved_transition or test_lane_managed_runner_projection' --junitxml=<private-output-file>
```

User previously approved isolated mode. Never invoke pytest directly or pass
positional test filenames to the wrapper. Once focused green, run the prior
combined managed selector plus all four new modules (target adoption, adoption
transaction, reserved transition, runner projection), reconcile the original
20 failing nodes including renamed equivalents, and record exact results.
Do not select the unrelated slow lane-helper suite accidentally. Finish strict
OpenSpec and whitespace validation. Close tasks only against full acceptance.

Do not test with real accounts, production credentials, real repositories, or
new runtime authority. Native children are not independent runners/mailboxes;
native swap/ctx/release/restore/continuation support remains gated. Do not
modify the pinned upstream submodule, workspace pointer, or lane registry by
hand. This checkpoint does not authorize launching or respawning a session.
