# Source-only containment diagnostic design

**Status: T046 passed its architecture/offline gates. T047, T048, and T049
passed Astra architecture review and Sol's canonical offline gates. T050 is
architecture approved and its focused gate passed 427 tests, 2,168 deselected,
zero failures.** The user authorized exactly one thirteenth Bite 4 run; it
exited 2, INCONCLUSIVE with `effect-or-observer-uncertain` after source
stop/removal and target-state volume creation but before copy, release, or
target creation. The inner source exception was not retained. An unbound
`parent_uuid` reference in the legacy/source runtime initializer is a
deterministic static cause candidate, not a directly proven historical
exception. Its authorization is consumed; two unattached labeled volumes
remain preserved. The user has since authorized exactly one fourteenth full
diagnostic run, pending push, Sol's post-push preflight/command review, and the
required command seal. This authorization permits no cleanup or deployment.
Bite 5 remains pending
and production unsupported. The source-only term describes
the source containment domain, not the whole experiment: a separate target
domain may start only after source exclusion, history custody, and durable
explicit release. The thirteenth result does not establish production
capability, loaded-history proof, or Bite 3 acceptance. The Bite 3
requirements in [stop-then-resume.md](stop-then-resume.md) remain authoritative.

The twelfth run and its separately authorized post-run cleanup remain in the
historical record below: all 19 volumes and five stopped containers in that
exact allowlist were removed, with its sealed bundle and 36-entry manifest
unchanged. That cleanup did not include the two volumes preserved by the later
thirteenth run.

## Thirteenth-run observation — INCONCLUSIVE

The user authorized exactly one run; Sol reviewed and froze the command. It
exited 2 after about 20 seconds. The sanitized report records overall
`INCONCLUSIVE`, `bite5_decision=pending-review`,
`production_disposition=unsupported`, and `support_claim=false`. The positive
arm is INCONCLUSIVE with `effect-or-observer-uncertain`,
`observer_complete=false`, `cleanup_complete=false`, and
`release_candidate_ready=false`. The negative arm is `not-run` with
`positive-release-candidate-not-established`, `positive-cleanup-incomplete`,
and `positive-observer-incomplete`. Explicit release was selected, but no
release or target launch occurred.

The source container was observed running after its phase, then stopped and
removed. The target-state volume was created before source-report schema
validation failed; copy, release, and target-container creation were not
reached. The inner source exception and event indices were not retained. The
unbound `parent_uuid` reference in the legacy/source initializer is a
deterministic static cause candidate, not direct proof of the historical
exception. Quarantine counters are zero, `volumes_removed=false`, and
`leftovers.manual_review_required=true`. There are zero labeled containers
and two unattached labeled volumes, one source-state and one target-state;
both remain preserved. At that thirteenth-run checkpoint, no retry, cleanup,
or fourteenth authorization was allowed.

Sealed manifest SHA-256:
`5815a42167d5a772131368264111f9cb124f726fe33e101dee318eb3f8bd9d23`.
Sanitized stdout:
`cd94d74854d88431c178b17b8893179e34b8821034e4570f02986051a86f374a`.
Private report:
`55d8311397fa473ee85612ea0e95c60ce6aa0caee074d2f360632964b6ab146e`.
Abort ledger:
`b898eabb9f181fdcbf8a0c00d11f36090417d9ad62059bc8a183072d8ba557a8`.
Runtime pins: SDK 0.2.153; CLI 2.1.273 SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`; image
SHA-256 `a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094`.

## Historical twelfth-run observation — INCONCLUSIVE

Sol's one authorized full invocation exited 2. The sanitized report records
`diagnostic_status=INCONCLUSIVE`, `bite5_decision=pending-review`,
`production_disposition=unsupported`, and `support_claim=false`. The positive
arm reason is `startup-task-event-observed`; the source terminal seed was
available, `observer_complete=true`, `release_candidate_ready=true`, and
`cleanup_complete=false`. The negative arm did not run.

Source stop event 34 and target stop event 151 were harness/engine enforced
with exit 137 and `oom=false`; source removal was event 36. Exact copy was
verified at event 92 and pre-release custody matched at event 119. Durable
release, launch intent, and target creation were events 120, 121, and 123.
Target removal was event 153, final helper removal event 179, and event 180
persisted final custody. One complete stopped target `system/task_notification`
matched session/task. Optional agent/tool identity remained unknown, and its
event UUID differed from the source parent. The sticky gate set
`history_query_allowed=false` after seeing the event; no history query or read
was sent, and no parent/child startup messages were observed.

Final custody retained the saved edit and linked source-parent history prefix.
The target parent JSONL grew from 52,825 to 55,372 bytes and
`other_config_mutation_count=1`, so custody does not establish whole
target-tree immutability. The generic negative-arm reason
`positive-release-candidate-not-established` is misleading because the
release candidate was ready; the unmet prerequisite was `cleanup_complete=false`
after preserving the INCONCLUSIVE run. The sealed result digest is
`4289f073b7c8508633f13c829d0ed670c813f917480ff106bd0525d14ee24294`; full
artifact hashes and inventory are in [`verification.md`](../verification.md).

The pre-cleanup inventory was 19 volumes (12 source-state, seven target-state),
four older stopped Bite 4 containers plus one stopped metadata diagnostic
container, zero running, and no current target container. The run itself
remains INCONCLUSIVE and supplies no loaded-history proof or Bite 3 OS
witness/all-path restart fence. Its resource inventory was later removed by
the separately authorized cleanup summarized above; Bite 5 remains pending
and production unsupported.

## Historical tenth-run observation — INCONCLUSIVE

The tenth invocation exited 2 with
`source-native-task-terminal-seed-unavailable`, detailed reason
`terminal-task-hook-evidence-incomplete`. Four lifecycle-v2 events were
complete: one started task with a tool-use ID; one hook callback was rejected
as `hook-tool-use-id-mismatch`; zero callbacks were stored or joined. The
rejection was correctly fail-closed, but the pinned SDK does not guarantee
callback/tool-ID equality and the retained summary lacks rejected-event kind
and digests. This cannot distinguish tool role, task, or association, and is
not evidence of a CLI defect.

Source stop/removal was harness/engine enforced with exit 137. Exact copy,
pre-release identity-linked custody, and final saved-edit/history-prefix
custody were retained. No release/target-launch ledger or target runtime
container was created; the negative arm did not run. The sealed result digest
is `addefcf9282109879c5fd1eaa74a199eb03949e8b81ed8c13b4728a837db8258`;
full artifact digests and preserved-resource inventory are in
[`verification.md`](../verification.md). No cleanup occurred. The tenth
authorization is consumed; no cleanup or eleventh attempt is authorized.

## Historical eleventh-run observation — INCONCLUSIVE

The v3 source seed was available through the SDK-sidecar proof and the source
projection marked the release candidate ready. Source and target stop/removal
were harness/engine enforced with exit 137. Exact copy, pre-release custody,
and final custody were retained. Durable release, target launch-intent, and
target-create events were 120, 121, and 123; final custody was event 180. The
target produced one complete stopped `task_notification` matching
session/task, while optional agent/tool identity remained unknown and the UUID
differed. The sticky history gate skipped its query. No parent/child startup
messages were seen and the negative arm did not run. The sealed result digest
is `9403d9910279ec0c6f047f53dc4d1c672751e90bb63d637985803c8202f04e5f`; full
artifact hashes and custody details are in [`verification.md`](../verification.md).

The post-run assessment is that the sticky gate behaved correctly under Bite
3. No replay or loaded-history proof exists. The next step is read-only
protocol investigation; a proposed progression-rule change requires separate
governance. Do not retry, clean resources, or attempt a twelfth run.

## Historical T048 source-seed bridge — architecture/offline PASS; runtime observation recorded

The tenth-run observation above is historical and unchanged. T048 addressed
the evidence gap without treating a structurally valid callback/task-tool ID
mismatch as a CLI failure: after complete callback-shape validation, retain
the callback as unresolved hook evidence, ACK it, preserve its observed tool
ID digest, and do not attach a task ID. Keep a bounded digest-only diagnostic
that distinguishes callback ID, hook-input ID, and current task/session/tool
IDs. Callback/input conflicts remain rejected and retain their own bounded
diagnostic; malformed, oversized, or overflow evidence remains fail-closed.

At source finalization only, a separate SDK-sidecar proof may link an
unresolved hook agent to the started Agent tool. The bridge must find unique
sidecar metadata whose `toolUseId` digest equals the observed task-start tool
ID, prove the SDK parent history's top-level session ID, and prove the child
history's top-level session and agent IDs agree with the hook. Candidate
paths only locate files; for `SubagentStop`, the hook's exact transcript path
must also match the safely opened child transcript. The bounded exhaustive
scan refuses symlinks, non-regular or multiply-linked files, duplicate-key
JSON, present parent-agent metadata, conflicting identities, and ambiguous or
missing evidence. It reads no message or tool body. The resulting distinct
SDK-sidecar proof is digest-only and strictly validated when constructed and
again after detachment under `native-task-source-seed-envelope-v3`, with the
separate `native-task-agent-proof-v2` / `native-task-sdk-sidecar-proof-v1`
schemas. Missing, conflicting,
ambiguous, malformed, or overflow evidence remains unavailable before
release. T048 passed the formal 243-test offline gate. The separately
authorized eleventh runtime attempt is recorded above; its authorization is
consumed and does not permit another attempt or cleanup. Bite 5 remains
undecided pending required evidence.

## Purpose and boundary

The diagnostic evaluates one disposable source runtime, its history, and an
exact-parent target startup after explicit release. The source and target run
in separate containers and never share a writable source-history volume. An
external observer and history custodian stay outside both runtime containers.
The source container is stopped and removed before any target container is
created. The report always carries `support_claim: false`.

The run uses only an immutable local image and the pinned SDK-selected CLI, a
scripted loopback service, and dummy credentials. It has no external network,
real account, live profile mutation, installation, deployment, or production
state. The target is created once, only after its durable explicit-release
record is bound to the frozen source-history manifest and exact parent UUID.

This diagnostic may observe a container lifecycle and bounded fixture facts.
Container stop/removal, `restart=no`, an empty observed process group, and a
successful target load do not establish continuous membership or escape
coverage for the original production POSIX PGID. They do not prove that every
production runner recreation path consumes a durable restart-deny fence. No
result from this diagnostic closes the Bite 3 production gate.

On any failed arm, the harness may issue one durable-intent-bounded stop to an
exact run-labelled container whose stop intent was not already recorded. It
preserves stopped containers and all volumes for manual custody review; it
does not force-remove evidence before a successful custody boundary.

## Candidate two-domain topology

This topology remains a design candidate. The ninth runtime attempt exercised
the source and copy/custody path, but ended before release and did not create a
target runtime container. The target-state volume was copied; no release or
target-launch ledger was created.

1. An orchestration process outside the runtime containers creates one
   run-specific source container from the immutable local image. It contains
   the source runtime and source fixture only. No target container or target
   process exists. The source runtime's scripted endpoint remains within its
   own container so its network stays disabled.
2. The source container has no network, host bind mount, host PID/IPC/UTS
   namespace, privilege, added capability, device, or ambient credential. It
   uses a read-only root, `cap-drop=ALL`, `no-new-privileges`, bounded process,
   memory and CPU limits, dummy credentials, and an explicitly disabled
   container restart policy. Effective settings are checked from engine
   inspection before launch and before the source runtime starts.
3. The source writes state to one unique engine-managed fixture volume mounted
   at one exact state root. Its fixed layout has separately inventoried
   `config/` and `workspace/` directories, plus `home/` and `xdg/`.
   `CLAUDE_CONFIG_DIR` points to `config/`, where the selected SDK writes its
   history; the diagnostic inventories allowlisted history files within that
   actual SDK store. The deterministic saved edit lives under `workspace/`,
   which is the source working directory. This is a deliberate exception to
   the current no-mounts validator: it is an engine-managed `volume`, never a
   host `bind`, and must be allowlisted by exact mount type, run identity, and
   destination. The external observer reads engine lifecycle events and
   inspection state from outside the source container. A loss, gap, or
   unexpected recreation makes the run inconclusive.
   Before requesting source stop, the orchestrator atomically persists and
   fsyncs a stop/removal intent in a private host-side ledger, bound to the
   operation, source invocation, and fixture owner/lineage/runner/daemon
   identities. The ledger is separate from the final report. An uncertain
   stop or removal effect is never retried.
4. After the observer records source stop, the source container is removed.
   Only then does a separate minimal helper container mount the source volume
   read-only. It verifies a bounded allowlisted tree and content digests, and
   writes an immutable source manifest outside the runtime containers. It
   does not modify source history or the saved edit.
5. A separate engine-managed target-state volume is created. A minimal copy
   helper, external to both runtime containers, reads the source volume
   read-only and copies the exact tree and bytes to the target volume. It
   copies the deterministic saved edit and verifies the copied tree against
   the source manifest. The copier exits and its writable target mount is
   removed before a separate read-only verifier inspects the target volume.
   The source volume remains immutable; the target container will receive
   only the target-state volume. No history content is serialized into the
   report.
6. After source custody and exact-copy verification, the orchestrator
   atomically persists and fsyncs one explicit release selection in the
   private host-side ledger. This is not a final JSON report boolean. The
   release is bound to the operation, source invocation,
   owner/lineage/runner/daemon fixture binding, source-removal observation digest,
   source manifest digest, target-spec fingerprint, target profile, and exact
   parent UUID. The durable release follows source stop/removal, custody, and
   exact-copy verification. It records a target-launch intent before one
   target creation and never retries an uncertain launch. Release and target
   launch intent records are atomically persisted and fsynced outside the
   runtime containers. The external observer verifies their order. Owner,
   lineage, runner, and daemon identifiers generated for the
   fixture are labeled as fixture identities; they are not observed
   production identities or an OS-domain witness. A missing, duplicate,
   stale, or mismatched release/intent refuses target startup and cannot be
   replayed.
   The bounded source runner enables native `SubagentStart`/`SubagentStop`
   hook callbacks so hook facts can be retained alongside lifecycle messages;
   callbacks remain observational and do not themselves prove task identity.
   Release also requires one complete source-observed v2 terminal-task seed.
   It contains separate bounded sanitized `task_started_event` and terminal
   `task_notification` records plus an authoritative `agent_proof`; it never
   rewrites the observed terminal's source-target correlation to manufacture
   target evidence. The start must be a `local_agent` observed in
   `source/setup` or `source/drain` strictly before the terminal notification.
   Session and task digests must agree with the actual active source runtime
   and with each other. The agent proof is either the agent identity directly
   observed on the started task, or a hook record joined exactly by the same
   session and tool-use ID (and by task ID when the hook record has one).
   Callback-time unresolved hooks may join later only through those exact
   digests; a missing hook tool-use ID remains unavailable. There is no
   single-child/cardinality or path-based inference. Reused tool-to-task or
   agent-to-task bindings, multiple agents for one exact join, conflicts,
   hook errors, malformed evidence, and any evidence overflow fail closed.
   Raw task, session, tool, and agent identifiers never cross the source phase.

   The target event shape is matched strictly by terminal subtype, status,
   session, and task. SDK-optional target fields that are absent remain
   unknown: absent `task_type`, `agent_id`, or `tool_use_id` is not invented and
   does not alone make the event incomplete; a present conflicting optional
   agent/tool identity rejects correlation. Source-side
   `source_target_correlation` remains all `unknown` until target observation.
   Lifecycle records use schema v2 to carry tool-use correlation explicitly.
   `task_updated.patch.status` (including `killed`) is recorded, and
   contradictory top-level/patch statuses are incomplete, but update-only
   evidence is not promoted to the v2 seed; only a terminal notification can
   seed this bounded tranche.

   The seed digest is bound to source invocation/parent and the source-phase
   digest; the envelope/digest are carried by both release and target-launch
   intents and the target specification. A bounded private source projection
   retains the unavailable reason, lifecycle summary, hook summary, and
   path-free ID-join diagnostics (seen/missing/mismatch/exact-candidate
   counts); the complete source phase digest binds these fields. It contains
   no raw IDs, hook payloads, paths, or transcript material. Missing,
   incomplete, ambiguous, or identity-unlinked seed evidence is INCONCLUSIVE
   before release and before target creation. A mismatched digest or
   parent/invocation binding refuses the target path. These are future-only
   diagnostic rules: they neither alter the already-completed ninth result nor
   grant another runtime attempt or production capability.
7. Only after the release and launch intent are durable, one separate target container is
   created with the same isolation policy. The exact pinned SDK/CLI resume
   path opens the exact parent against the verified target working copy. The
   target initializes native-task correlation from the validated sanitized
   source seed using the existing strict event/identity rules. Under the
   default `strict-v1` mode, the seed does not satisfy or bypass the sticky
   startup-activity gate; any observed native task event still blocks the
   optional history query. T049's separately selected diagnostic-only mode is
   governed by the exact exception below and does not change the strict gate.
   Target history is checked for preservation of the source byte prefix after
   the bounded startup observation. A successful argument or initialization
   alone is not exact parent restoration.
8. After the bounded target startup observation, the target is stopped using
   the frozen harness action and its writer exclusion is observed. Only after
   that boundary does the external custodian mount the target volume
   read-only and verify its bounded tree and source byte prefixes. If target
   writers cannot be excluded, final target custody is unknown. Cleanup
   removes runtime containers and run volumes only after custody and manifest
   verification finish.

Every history and fixture tree walk is bounded and relative to an opened root.
The custodian/copy helper refuses symlinks, non-regular files, hard-linked
files, path escapes, duplicate paths, excessive depth, excess entries, and
oversized files. It opens files without following links and verifies file
identity and size before and after reads. The validator does not use
`resolve()` followed by an unchecked open as a containment boundary.

After source custody, the copy helper is stopped and removed before the
read-only target verifier runs. The verifier is stopped and removed before
the read-only pre-release history custodian. That custodian requires exactly
one source JSONL whose bytes begin with the identity-linked parent prefix
captured during the source phase, then verifies the complete stopped-source
JSONL is an exact prefix of the copied target JSONL. Missing or ambiguous
identity linkage is inconclusive; a witnessed copy mismatch fails. It emits
bounded path-free facts and digests, which are bound into both durable release
and target-launch intents. Before release, the external observer reconciles
expected event identities with the live run-labelled engine inventory and
requires the source and every helper to be destroyed, no target or other live
container, no writable helper mount still attached, no unresolved create
intent, and exactly the two expected engine volumes. The source and target run
volumes are therefore not writable by any helper at release time. The existing
`validate_isolation` remains unchanged; the new entrypoint uses a distinct
validator for this topology.

The no-persistent-mount alternative remains blocked unless an independently
verified freeze/export path can preserve source history after source shutdown,
copy it byte-for-byte, and inspect it without changing the source bytes. A
host bind mount is not an allowed fallback.

## Isolation and evidence rules

The proposed validator checks effective engine configuration, not only create
arguments. In addition to network, privilege, namespace, capability, device,
root-filesystem, no-new-privileges, resource, and host-mount checks, it
requires:

- source and target containers have distinct engine identities and distinct
  runtime domains; the source is stopped and removed before target creation;
- exactly one run-specific engine-managed fixture volume is mounted at the
  exact source state root, with separately inventoried actual SDK `config/`
  history store and `workspace/` subdirectories at stable paths;
- a separate target-state volume is byte-for-byte verified, including the
  deterministic saved edit, before release;
- source volume trees contain only bounded regular files with link count one;
  symlinks, hard links, path traversal, and mutation during read refuse;
- source and target volumes are detached from writable copy/verifier helpers
  before release; target volume is mounted read-only for final custody only
  after target stop and writer exclusion;
- the unchanged legacy `validate_isolation` remains untouched; a distinct
  validator enforces this new exact engine-volume topology and restart policy;
- no host bind, `VolumesFrom`, unexpected mount, or additional writable
  history copy exists;
- effective restart policy is explicitly `no` with no retry count on source,
  target, and helper containers; and
- no target exists before the release record, and at most one target launch is
  associated with that record.

The positive arm selects explicit release. Its durable record binds the
source invocation and owner/lineage/runner/daemon identities, source-removal
observation digest, source manifest digest, exact target-spec fingerprint,
target profile, and exact parent UUID. The external controller writes a
stop/removal intent before the stop effect and a target-launch intent before
the create effect. If either effect's result is uncertain, it does not replay
the action or create another target. A separate negative arm selects that
same otherwise-valid explicit-release input while injecting an unknown
effect; it must refuse specifically for the effect and create no target. The
negative arm uses fresh run IDs and volumes. It is not satisfied by merely
withholding release.

The observer emits a bounded sanitized manifest containing a local monotonic
observation sequence, run/container digests, lifecycle events, effective
isolation facts, source and target custody outcomes, source stop/removal
intent and observation digests, release and target-launch intent digests,
cleanup outcome, and reason codes. It excludes credentials, event bodies,
transcript text, process paths, raw process/container identifiers, and history
paths. Missing, truncated, conflicting, or gapped observations remain
unknown. Observer failure never becomes an empty-process or successful-stop
claim.

The custodian records only allowlisted file counts, bounded sizes, content
digests, exact-copy results, and byte-prefix preservation. It reads source
state only after source stop/removal and target state only after target stop
and writer exclusion. Stored bytes surviving shutdown do not prove that the
runtime loaded or restored them. The diagnostic does not query, modify,
delete, or rewrite native history.

## Current producer feasibility

Static inspection found no production producer for Bite 3's required
source-exclusion and restart-domain evidence. The current runner uses
`start_new_session=True`; `_process_evidence` reports its own PID, PGID, SID,
and a process-start token; shutdown signals the original owned PGID and checks
whether that PGID is alive. Those facts do not provide loss-aware,
launch-to-exclusion membership and escape coverage, detect every fork,
reparent, `setpgid` or `setsid` transition, or prove that the entire source
domain is empty.

The current production lifecycle also has no durable restart-deny fence shown
to be enforced by every runner creation, recovery, fresh-adapter, daemon
takeover, and external-supervisor path. `restart=no` on diagnostic containers
disables one engine policy only; it does not inventory or fence other actors
that can recreate source work. The candidate observer and custodian do not
repair either gap.

**Feasibility disposition:** Astra reviewed the two-domain diagnostic and
history-custody design. T046's candidate validator and opt-in orchestrator
passed architecture review and the focused offline gate. The ninth runtime
attempt exercised the missing-seed refusal, with source stop/removal, exact
copy, identity-linked pre-release custody, and final copied-volume custody
observed; its harness/engine-enforced source-container exit 137 is not natural
graph shutdown or production containment. The source projection did not retain
the detailed unavailable-reason envelope, and no release/target-launch ledger
or target runtime container was created. Available-seed transfer and target
fingerprint/correlation/startup/history query remain unexercised. An
authoritative production evidence producer is not feasible with the current
producer or this topology. Production remains unsupported at preflight until a
separately reviewed OS-domain witness provides continuous loss-aware coverage
and a durable fence is enforced across every source recreation path. If either
condition cannot be established, retain the fail-closed refusal in the Bite 3
contract.

## Acceptance and refusal matrix

| Observation | Diagnostic disposition | Production disposition |
| --- | --- | --- |
| Isolated source stops; source custody and exact target copy match; release precedes the sole target creation; exact parent and saved-file evidence correlate | Bounded diagnostic observations pass; still `support_claim: false` | Not PGID membership/escape proof and not an all-path restart fence |
| Target exists before release, or source and target share a runtime container or writable history volume | Refuse; preserve artifacts and do not retry | Unsupported |
| Wrong restart policy, host bind, extra mount/container, or invalid custodian permissions | Refuse before launch or report inconclusive | Unsupported |
| A witnessed source/target ordering violation, source recreation after its fence, unauthorized request, changed saved edit, byte-copy mismatch, duplicate target, forbidden link/path shape, or wrong parent UUID | **FAIL**; preserve evidence and do not retry | Unsupported or indeterminate under Bite 3 |
| Observer gap, unobserved writer, missing/ambiguous identity, unreadable or oversized history, unknown custody result, or cleanup before custody | **INCONCLUSIVE**; preserve evidence and reason codes; do not launch a second target | Indeterminate if source stop may have been dispatched; no further launch or release |
| Separate explicit-release negative arm injects an otherwise-unknown effect and refuses specifically for it without release/target | Negative control passes; Bite 5 verdict still requires all Bite 3 source evidence | Does not establish production containment |
| Any production creation/recovery/takeover path lacks fence enforcement, or OS-domain coverage is missing | Not applicable to the diagnostic | Unsupported preflight refusal; after possible stop, remain indeterminate and retain claims |

## Historical T046 offline validation gate completed before the ninth run

The focused offline gate passed on the frozen T046 candidate before the ninth
run. It covered the topology validator, release ordering, history copier, and
sanitized manifest. The tests reject
host binds, network, elevated capabilities, host namespace joins, missing or
changed restart settings, writable custodian mounts, extra containers,
target creation before release, duplicate release or target launch, source
and target volume reuse, symlink/hard-link/path escape, non-regular or
mutating files, byte-copy mismatch, target custody before writer exclusion,
event gaps, unexpected source recreation, cleanup-before-custody, oversized
data, and malformed/private fields. They verify bounded manifest serialization
and ensure reports contain no raw IDs, paths, credentials, or bodies. Sol's
canonical focused gate passed 155 selected tests with zero failures, errors,
or skips in 5.715 seconds; hashes and output digests are in
[`verification.md`](../verification.md). Offline success validates the
harness contract only, not containment or runtime support.

No production code, installation, account activation, deployment, commit, or
push is authorized by this design slice. Bite 4 is the bounded two-domain
runtime experiment described by [runbook.md](../runbook.md); Sol High is its
sole test/runtime executor. The ninth and tenth runs' unavailable-seed
refusals are INCONCLUSIVE and do not close Bite 4 or Bite 5. The tenth's
handler rejection was fail-closed, but the SDK does not guarantee callback
tool-ID equality and the retained summary lacks rejected-event kind/digests;
this is not a CLI-defect finding. At the T047 checkpoint, both then-existing
run authorizations were consumed and no eleventh attempt had yet been
authorized. T048 and the later consumed eleventh authorization are recorded at
the top of this document. Bite 5 remains undecided and production unsupported.
No cleanup, retry, or twelfth attempt is authorized.

## T049 separate diagnostic-only history-query progression

T049 is an offline-only candidate. The twelfth Bite 4 run remains historical
`INCONCLUSIVE` with `startup-task-event-observed`; Bite 5 remains pending and
production remains unsupported. No runtime retry, cleanup, or production use
is authorized by this contract update.

The existing `strict-v1` history-query mode remains the default. Its
`assess_v1_history_query_gate` behavior is unchanged: a task notification still
skips the optional history query. The separate
`two-domain-terminal-task-diagnostic-v1` mode must be selected explicitly in
the target profile and bound by the target-spec fingerprint and durable
release and launch intents. The seed cannot select the mode or grant the
exception by itself.

This mode can authorize one diagnostic query only when all startup evidence
is complete and exact:

* The validated source seed contains a `stopped` terminal
  `system/task_notification` and its matching earlier `local_agent`
  `task_started` record, bound to the source invocation and exact parent
  session. The target contributes exactly one complete
  `system/task_notification` with `status=stopped`, exact parent-session and
  task-ID matches, and no conflicting optional agent/tool IDs. Target
  `task_type` may be absent or null as emitted by the pinned SDK; the source
  started record supplies the `local_agent` constraint. Do not synthesize a
  target task type. The native notification frame has no `origin` field; a
  present origin refuses the exception.
* The target emits exactly one successful injected startup result with
  explicit `origin.kind=task-notification`, a top-level session ID equal to the
  exact parent, `is_error=false`, and no error, abort, or deferred-tool
  evidence. Missing/unknown origins, wrong parent, or an absent result refuse.
* Startup has no other task lifecycle event, assistant/tool activity,
  unexpected frame or route, gateway request or in-flight arrival, overflow,
  ambiguity, unparsed or partial frame, or reader error. Request observation
  begins before `Popen`; the gateway stays in a held/deny phase while startup
  is observed, so an unexpected startup request is refused and remains visible
  in the evidence.

If admitted, the probe creates a fresh private query nonce and a distinct
unpredictable response challenge, and sends exactly one neutral user frame
with `origin.kind=human`. The gateway admits exactly one parent
`/v1/messages` request with the selected model and dummy authorization. In
that same request, direct role-correct content blocks must show the source
prompt marker, exact Agent tool-use and matching tool result, in that order,
before the final user message containing the nonce. Nested tool objects,
facts split across requests, extra tool events, child requests, other routes,
duplicate JSON keys, and invalid model/auth refuse. The gateway emits only
the challenge and records the request-facts digest, response-message-ID
digest, successful complete response write, and closed query window.

Query completion requires exactly one fresh post-query assistant frame and
successful result, exact parent session, explicit human origin, and exact
challenge text. If the stream exposes an assistant message ID, its digest must
match the gateway response ID digest; if omitted, exactly one assistant frame
with an explicitly absent ID is allowed. Errors, aborts including
`aborted_*`, deferred tool-use data, partial/unparsed frames, reader failure,
or missing stdout EOF refuse completion. The gateway must be shut down and
fenced before its final arrival snapshot; there must be exactly one total
query-phase parent request, no child/other route or in-flight arrival, and no
overflow. The target must exit and total native task events must remain one
through the post-query drain; a late task or request invalidates completion.

This evidence is terminal-correlation-only. It proves that the listed bounded
source facts reached the target model request and that the target returned the
fresh challenge; it does not prove that the full history was restored or
loaded, replay, quiescence, child restoration, or production capability. The
positive and negative arms must both be observed before the overall diagnostic
may say `OBSERVED`. No T049 offline result changes the historical Bite 4
disposition or closes Bite 5.

## T050 future-only source-report failure correction

The thirteenth run remains historical INCONCLUSIVE. Its sealed report did not
retain the inner source exception; the unbound `parent_uuid` reference in the
legacy/source initializer is a deterministic static cause candidate, not a
directly proven historical exception. T050 changes future offline behavior
only and grants no runtime authority. A separate user authorization now covers
exactly one fourteenth diagnostic run after push, pending Sol preflight/command
review, and required command seal; no cleanup or deployment is authorized.

Remove that unbound initializer and limit generic fallback `error_site` to an
allowlisted component/function and integer line from the probe traceback; do
not publish exception text, paths, or locals. Immediately after source
`_runtime_exec` returns, persist the exact mapping and invocation, container,
and report digests using the private append-once bounded writer, before source
stop/removal or target-volume creation. Validate source schema/phase,
`support_claim=false`, `target_code_reached=false`, and exact source bindings
before progression. A malformed/fallback mapping remains in private evidence
and returns the fixed public `source-runtime-report-invalid` INCONCLUSIVE
result through quarantine. An otherwise-valid explicit
`target_code_reached=true` remains FAIL; missing or unknown reach evidence
remains INCONCLUSIVE.

Astra approved the T050 architecture; Sol's canonical focused gate passed 427
tests, 2,168 deselected, zero failures. The gate does not revise the
thirteenth run, grant another runtime authorization, establish Bite 3
containment or loaded-history proof, decide Bite 5, or enable production.
