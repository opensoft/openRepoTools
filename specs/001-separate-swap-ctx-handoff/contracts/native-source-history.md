# Offline native source history and adoption assessment

This bounded prerequisite implements parts of T008, T010 and T014. It does
not adopt a target, enable native swap/ctx, grant a capability, or authorize
an open, release, send, shutdown or claim transfer. Runtime acceptance remains
governed by [recovery-lifecycle.md](recovery-lifecycle.md).

## Immutable source archive

The internal controller method
`archive_native_source(archive_id, operation_id, generation)` records a
validated source snapshot under the existing controller transaction. It
requires current managed owner/daemon authority, a fenced native context and
the matching active paused/indeterminate operation. It copies the mechanical
controller snapshot, excluding the archive collection itself. No transcript,
credential or generated checkpoint body is introduced.

`native_source_archives` is an additive schema-v2 controller collection. Its
entries have the native marker, `record_kind: native-source-archive`,
`archive_id`, `operation_id`, `source_identity`, `snapshot_digest`, and
`snapshot`. Source identity binds owner generation, lineage ID/generation,
coordinator session, runner incarnation and invocation. The digest covers the
canonical complete snapshot, not just its identity. Archive IDs are unique;
an exact retry returns the existing archive without another write or journal
event, while changed source content under the same ID refuses. Copying a
source does not close its observations or erase its active records.

There are at most 16 archives and the existing one-MiB controller-record limit
still applies to the complete record. Capacity refuses before persistence;
history is never silently evicted. Every archive is independently validated
against its own source snapshot, including admission/stop/interrupt evidence
and operation linkage, not the current active context. Nested archives,
unknown archive fields, mismatched identity/digest, malformed historical
evidence and non-fenced source snapshots refuse reload. Historical validation
is read-only and cannot consult a runtime or modify the current controller.

`native_source_archive(archive_id)` returns a defensive copy under the same
read transaction. Status exposes bounded archive identity/digest summaries,
not another full copy of each controller snapshot. The absent collection on
an existing schema-v2 record means no archives; a present malformed collection
does not. Existing schema-v1 refusal remains unchanged.

## Read-only claim adoption assessment

The internal state method
`assess_lineage_workspace_adoption(expected_source_claim,
expected_target_claim, *, expected_daemon_id)` reads the existing global
claim index under its lock. It does not create a transfer intent, append a
journal, change the index/owner/controller, or issue a runtime action.

Both expected snapshots must be strict typed workspace claims. The target
differs only in lineage ID, bound coordinator identity and lineage generation
(exactly source + 1); owner generation, policy, workspace, repository, host,
lane and claim timestamp remain identical. Owner generation and daemon must
be current and owner/recovery state consistent; pending recovery refuses.
Unbound source/target identities refuse; reused identities yield
`indeterminate`, never a held result.

An exact sole source with no conflicting target identity/path yields
`source-held`. An exact sole target with the source absent and no conflicting
source/target identity/path yields `target-held`. Both, neither, changed,
duplicate or overlapping claims, retained source child claims, or incompatible
pinned owner identities yield `indeterminate` with explicit reasons. Malformed
durable state still refuses. There is no inference of death, quiescence,
transfer success or permission to replay from either held result.

The future adoption transaction must durably bind a source archive, source
and target claims, operation and daemon identity before the claim-index CAS.
Only that recorded intent plus separately verified runtime evidence may allow
a reconciler to finish controller adoption after a target-held result. A
source-held result never authorizes an automatic CAS retry or target open.
This slice supplies preservation and assessment. The separately governed
[internal adoption transaction](native-adoption-transaction.md) specifies
durable intent and held ownership acknowledgement; it still does not publish
or open a target runtime.
