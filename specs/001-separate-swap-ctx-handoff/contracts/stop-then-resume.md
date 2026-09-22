# Stop-then-resume v1 contract

Authority: [approved decision](../../../openspec/changes/separate-swap-ctx-handoff/stop-then-resume-decision.md).

## Scope and compatibility

The explicit discriminator is `stop-then-resume-v1`. It selects a new
transaction, not weakened validation of `metadata.native_swap`. Omitted mode
continues to mean the existing strict behavior; unknown mode values refuse.
Persist the discriminator in request identity and durable operation metadata.
Release and recovery route by the stored mode, not a later caller override.
Old records remain byte-compatible and retain their original proof requirements.

## State and ordering

| State | Permitted work | Target runtime |
| --- | --- | --- |
| preflight | Read profile/history/settings and validate source capability | Absent |
| source-stopping | Persist intent, fence, invoke supported bounded stop once | Absent |
| ready-to-resume | Source exclusion and effect accounting proven; archive and exact target spec bound; claims retained | Absent |
| release-authorized | Persist exact authorization and at-most-once launch intent | Startup now permitted |
| target-starting | Exact UUID resume under the selected profile; reconcile native startup | May infer under release authority |
| released | Actual exact parent/account validated and child outcomes accounted for | Active |
| indeterminate | Preserve claims, intents, evidence and unknown effects; observe only | Never create a replacement automatically |

These are v1 lifecycle states, not assertions that all are implemented. A
target startup failure after authorization is not a return to held status.
No daemon pump or additional child restart is allowed until startup has been
accounted for. Startup orphan activity after release does not prove exact
child recovery and cannot justify sending a duplicate restart instruction.

## Minimum authoritative facts

Before destructive source stop, bind owner/generation, source runtime and
invocation identities, actual native child identities and policies, complete
writer/tool/effect accounting, and an explicitly selected compatible profile.
The source capability must describe the actual launch/containment domain and
whether any external supervisor can recreate the runtime. The implementation
must refuse unsupported configurations before changing the running source.

Before readiness, require observed exclusion of that whole source domain and
reconciled effects. Killing an owned PGID, interrupt ACK, missing PID, or
terminal parent Agent tool event alone is insufficient. Never treat missing
native durable orphan-clear evidence as successful clearing: v1 does not need
that strict-mode receipt, but still needs source exclusion and effect safety.
Unmanaged detached work or unknown remote mutation remains unresolved.
Unlike strict mode's graceful drain-before-parent-shutdown ordering, v1 may
mechanically contain unfinished child/tool work first. It must still reconcile
complete exclusion and effects before readiness; termination is not completion.

Archive immutable mechanical facts and bind parent/child transcript references
and a bounded integrity manifest to the source archive and exact target spec.
The controller archive itself contains no transcript bodies and is not a
backup of those histories. Verify history availability and integrity without
editing it. Dirty and untracked workspace files remain untouched. Claims stay
with one lineage through the entire transition.

At release, revalidate source exclusion, claim ownership, history manifest,
target profile/settings and operation/generation. Persist a digest-bound
authorization and launch intent before runtime creation. Only the official
exact parent resume path is allowed; no fresh context fallback. The SDK path
must explicitly understand release-authorized startup: do not reuse a held
startup path while pretending its orphan checks passed.

No phase initiates source model work or requires source quota. Separate
already-in-flight requests, any unexpected new source requests during stopping,
and released target requests in evidence. Unexpected/unknown stop behavior
does not silently pass because the target was deferred.

## Retry and recovery

Each side-effecting stop/start is preceded by a durable intent and follows
at-most-once dispatch. Lost ACKs or crashes after intent are unresolved until
read-only correlated evidence proves what happened. Recovery never repeats an
uncertain stop, starts a second target, infers release from target selection,
or changes to strict/legacy mode. A stale generation, changed profile, altered
manifest or mismatched exact UUID refuses. Claims and discovery remain until
safe explicit unenrollment; child-worktree claims precede lineage claim release.

## Smallest experiment before public implementation

Extend the existing isolated no-auth scripted-runtime harness with a distinct
v1 mode. Use the pinned SDK/CLI and immutable local container image, no pull,
network disabled, no host mounts, dummy credentials, bounded resources and a
new private report. Preserve existing probe semantics.

The positive arm must observe an unfinished native child and tracked shell,
create/hash a deterministic disposable workspace edit, stop/contain the source,
retain exact history, prove no target exists before explicit release, and only
then attempt exact SDK resume. Native stop facts and harness-enforced process
termination must be reported separately. Check the edit remains byte-identical.
The negative arm injects unknown effect accounting and proves target startup
is refused even when local PIDs disappeared. Unsupported facts remain unknown.

A positive restoration verdict requires observed exact parent identity and
retained pre-stop history, not just correct loader arguments or initialization.
Missing identity/history evidence is inconclusive. The negative arm must supply
an otherwise valid explicit release and refuse specifically for unknown effects,
authorizing neither readiness nor launch. Merely withholding release cannot
count as a successful unknown-effect refusal test.

This fixture can establish ordering and scoped observations, not actual-account
support or unrestricted complete host containment. Its report always carries
`support_claim: false`. Authenticate no account, switch no real profile, and
activate no live lane on the strength of this experiment.

### Startup-event and stored-history diagnostic follow-up

The first release arm observed a startup task event and therefore skipped its
history query. Under T003/T004, capture bounded, sanitized lifecycle facts:
observed event kind/status, digested native identities, local observation order,
and source/target identity matches only where those fields actually exist.
Missing, ambiguous or truncated observations remain explicit. Never log event
bodies, transcript text, raw identifiers or local history paths.

Observe the source history while active, again after source exclusion before
target creation, and after the bounded startup observation before cleanup.
Attribute parent/child histories only through observed identity/link evidence;
filename-only matches remain candidates. Record bounded content
integrity and, where history legitimately grows, preservation of the original
byte prefix. An unreadable, missing, changed, oversized or uncorrelated history
is not preserved by assumption. Stored bytes remaining intact does not prove
the runtime loaded them or resumed the associated child.

Keep the existing sticky startup-activity gate: even a source-correlated
terminal notification does not prove all restored work has been reconciled.
This diagnostic adds no history query, restart, launch retry, production
capability or automatic release permission. A safe progression rule requires
separate authoritative evidence; this observation slice cannot supply one by
relabeling a task event.
