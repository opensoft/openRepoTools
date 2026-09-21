# Internal native claim-adoption transaction

This T008/T010/T014 slice connects immutable source history to claim transfer
and durable controller acknowledgement. It performs **no runtime action** and
does not replace the active coordinator, create an invocation, clear source
ledgers, mark an operation ready/released, or enable a public swap/ctx route.
The committed target is an ownership descriptor for later held-runtime
integration, not proof that a target runtime has loaded. In particular, an
adoption `target-held` assessment is a claim-ownership descriptor, not a
runtime-held target. The full runtime gates in `recovery-lifecycle.md` remain
prerequisites for that integration.

## Authority and evidence

The controller takes its existing store transaction (the real store's global
exclusive lock), reloads, and binds an adoption to a current managed owner,
trusted coordinator-interrupt daemon, fenced native source, active paused or
indeterminate operation, and independently validated source archive. Exact
source and target claims follow `native-source-history.md`; the target changes
only lineage ID, coordinator UUID and lineage generation (+1).

A new **internal constructor-injected**, synchronous evidence provider is
required for preparation, explicit advancement and controller reconciliation.
It is absent by default and is never populated by a public request, runner
specification, stored boolean or the scripted probe. Its bounded response
must bind the adoption/operation, owner/daemon, archive digest, source identity,
and source/target claim digests, plus a runtime identity digest and opaque
evidence reference. It must positively attest source-writer exclusion,
resolved source effects, supported durable native-worker-state clearing,
continuous control-epoch request freedom, and supported target-startup hold.
Missing, false, unknown, stale, malformed or differently bound evidence refuses
before the claim effect. There is no production provider in this slice.
Fake-provider tests exercise the transaction only, not runtime acceptance.

The constructor seam is `_native_adoption_evidence_provider(binding)`.
`binding` contains exactly `adoption_id`, `archive_id`, `archive_digest`,
`operation_id`, `owner_generation`, `expected_daemon_id`, `source_identity`,
`source_claim_digest`, and `target_claim_digest`. The response repeats those
bindings exactly and adds `runtime_identity_digest`, `evidence_reference`, and
five literal-true facts: `source_writers_excluded`, `source_effects_resolved`,
`native_worker_state_cleared`, `control_epoch_request_free`, and
`target_startup_hold_supported`. Its complete canonical digest is
`evidence_digest`; asynchronous or unknown-field responses refuse.

## Durable records

The state store owns `native-adoptions.json`, a schema-v2
`native-adoption-ledger` with an `intents` map. At most 16 intents and the
existing one-MiB record limit are allowed; exhaustion refuses without eviction.
Each strict `native-adoption-intent` binds:

- adoption ID, archive ID/digest, operation ID, owner generation and daemon;
- the archived source identity and full exact source/target claim snapshots;
- canonical claim digests and the validated evidence digest, runtime identity
  digest and evidence reference;
- an immutable intent digest, phase, and optional final controller digest.

The exact entry keys are the native marker plus `adoption_id`, `archive_id`,
`archive_digest`, `operation_id`, `owner_generation`, `expected_daemon_id`,
`source_identity`, `source_claim`, `target_claim`, `source_claim_digest`,
`target_claim_digest`, `evidence_digest`, `runtime_identity_digest`,
`evidence_reference`, `intent_digest`, `phase`, and `controller_commit_digest`.
`archive_digest` is the source archive's `snapshot_digest`.
`controller_commit_digest` is null until finalization and is then the
immutable finalized adoption checkpoint. It is not recomputed as a later
mutable controller digest. The intent digest excludes itself, its mutable
phase and final controller digest.
Unknown fields, changed IDs/digests, invalid claim pairs or malformed existing
records refuse. Same-ID retries must have identical immutable content.
A competing intent for the same operation/source cannot manufacture another
CAS authorization. Absence of this file means no intents, not success.

The controller's operation metadata holds a bounded `native_adoption`
reference/acknowledgement binding the same adoption, intent, archive and target
claim digests. It does not embed another controller snapshot. Existing archive
schemas and independent historical validation remain unchanged.
That metadata has exactly `adoption_id`, `intent_digest`, `archive_id`,
`archive_digest`, `target_claim_digest`, and `phase`; its phase remains
`prepared` until the controller acknowledgement is `controller-committed`.

Internal controller methods are `prepare_native_adoption(adoption_id,
archive_id, operation_id, generation, source_claim, target_claim)`,
`advance_native_adoption(adoption_id)`, `recover_native_adoption(adoption_id)`,
and observational `native_adoption(adoption_id)`.
The state methods are `prepare_lineage_adoption(intent)`,
`apply_lineage_adoption(adoption_id, *, expected_daemon_id, authoritative=False)`,
`reconcile_lineage_adoption(adoption_id, *, expected_daemon_id)`,
`finalize_lineage_adoption(adoption_id, *, expected_daemon_id, controller_digest)`,
and observational `read_lineage_adoption(adoption_id)`. The `authoritative`
argument is only an internal caller precondition; the controller must obtain
fresh bound evidence before passing it. It is not an evidence source.

## Ordered phases and crash boundaries

1. Controller preparation persists its exact adoption reference before the
   state store can create a `prepared` intent. Preparation never changes claims.
2. Explicit advancement revalidates fresh evidence and all durable bindings,
   then persists `claim-cas-pending` **before** calling the existing exact
   one-row claim CAS. Only a previously `prepared` intent may issue that CAS.
3. An exact target-held **claim** assessment after the authorized CAS records
   `claim-transferred`. This is an ownership descriptor only, not proof that a
   target runtime is held or that `runtime.open` has occurred. There is no
   automatic retry after a possible CAS.
4. The controller persists `controller-committed` acknowledgement and the
   target ownership descriptor, keeping its operation paused/indeterminate,
   active source context fenced and all archived/active history intact.
5. State finalization reads and validates that actual durable controller
   acknowledgement, binds its canonical record digest, and records
   `controller-committed`. No cleanup or deletion is implicit.

State functions never call back into the controller or await a runtime. All
cross-file ordering uses the same global lock; this serializes writers but
does not make file replacements crash-atomic. Journals are diagnostic, never
the authority for concluding a claim replacement or controller commit.

## Native ctx publication bridge

The existing adoption transaction is consumed by native `ctx` only in this
strict order: fence A, drain the native graph, and prove supported worker-state
clear plus process/effect exclusion; validate the immutable source archive under
its original A context while retaining A's source claim, UUID, and lineage;
prepare and advance the existing adoption; finalize its claim-owned descriptor;
persist the exact
target-open intent; perform the actual target `runtime.open` in held mode;
recheck target readiness, current owner/daemon, and target claim; then perform
one controller write that publishes the target participant/startup, retires
A's live ledgers into the archive, queues the caller checkpoint and child
dispositions, and installs the exact immutable
`operation.metadata.native_ctx_publication` record defined in
`data-model.md`. The record is absent before that atomic activation and has no
prepared/publication phase enum; the existing ctx/open intent owns those
windows.

All target publication fields must join the immutable launch specification,
held-open evidence, and adoption target claim. The target keeps the same
profile and owner generation, but has a new coordinator UUID, new lineage,
lineage generation A+1, and new runner incarnation. Its target startup
specification removes any inherited `native_swap_target` marker. The prior
`metadata.native_adoption` reference remains unchanged, and its
`controller_commit_digest` remains the finalized historical checkpoint rather
than a required match for a later mutable controller digest.

After publication, an exact completed `ctx` retry or getter validates the
immutable adoption/publication joins and current target authority when an
action is requested. It does not re-enter source-only advancement or CAS
checks and does not reopen A after A has been fenced, archived, and retired.
A lost publication acknowledgement may recognize only the same immutable
receipt; a missing or changed join refuses. Claims persist through CAS/open
uncertainty and are never rolled back. Incompatible isolated-child
multi-transfer remains unsupported; this bridge adds no new transfer
mechanics or production provider/proof.

## Recovery

Recovery may inspect/update transaction records and finish a provable
controller acknowledgement. It never opens, sends, releases, interrupts,
shuts down, clears runtime state, or retries the CAS.

- A missing intent or a still-prepared intent with unexpected target ownership
  is indeterminate, not evidence that this transaction transferred the claim.
- Source-held after `claim-cas-pending` stays indeterminate: even when no effect
  is visible, recovery does not issue the CAS again.
- An exact target-held claim descriptor after a durable possible-CAS phase may
  finish bookkeeping only with matching archive/controller bindings and fresh
  trusted evidence; it is not runtime-held evidence.
- Both, neither, changed/duplicate/overlapping claims, retained source child
  claims, identity reuse, owner pins, pending owner recovery, or changed owner,
  daemon, generation, archive or evidence retain/refuse uncertainty.
- An atomic controller commit followed by a journal/finalization failure is
  recognized on reload; no rollback, second CAS or runtime action follows.

Identical completed retries do not append another journal event or write.
Status/getters return defensive copies and are observational. Target-runtime
publication and source-ledger rollover are performed only by the native ctx
publication bridge above; this adoption transaction alone does not perform
that runtime integration.
