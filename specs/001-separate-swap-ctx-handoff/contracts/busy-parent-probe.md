# Bounded busy-parent runtime observation

This T003/T030 investigation is a scripted loopback experiment, not a native
runtime capability or an authenticated account test. The pinned SDK, executable
digest, network-none sandbox, empty private configuration, and explicit
post-hold release constraints in `recovery-lifecycle.md` remain unchanged.

## Positive entry witness

An opt-in busy-parent arm must positively identify a parent Messages request
continuing the source Agent tool result and withhold that response at a
gateway barrier. The real native child and its tracked Bash process must be
observed active immediately before entry, with no terminal child event already
observed. This is a pre-entry liveness observation, not an atomic process check
under the gateway lock. Under that lock, control entry records the exact
pending request index, continuation classification, barrier state and epoch
boundary. Merely not having read a parent result is not a busy-parent witness.

The barrier does not issue another model request or alter native transcripts.
It prevents the scripted response from completing until explicit fixture
cleanup. The busy arm skips the settled-parent wait and sends the documented
coordinator interrupt while that response is withheld. Deadline expiry,
premature barrier release, missing child/process evidence, ambiguous parent
classification, or lost observation makes the busy case inconclusive; it
must not fall back to a settled-parent success.

## Observation and cleanup

The same arrival-time Messages counter covers one sticky epoch from control
entry through stopping and target-held initialization until explicit release.
The already-arrived blocked request is reported separately from new arrivals
within the epoch; its index must precede the epoch's first arrival index.
Response completion is recorded only after the HTTP response write succeeds
and does not recategorize an arrival.
Post-release traffic is reported separately, with no counter reset.

Barrier waits are bounded and cleanup always releases the fixture barrier so
server threads cannot keep a disposable sandbox alive. Client cancellation,
response completion, control receipt, child/tool terminal facts, process exit,
forced cleanup and observer coverage are independent facts. An interrupt
receipt alone proves neither cancellation of the pending request nor graph
quiescence. Any forced cleanup is reported, not converted into native stop
evidence. Only the sandbox created for this run may be removed.

Positive orphan-wake and durable worker-state-clear observations require a
supported runtime observation surface. The existing unfinished-child arm may
be used as a negative/unknown control, but absence of traffic or task frames
does not prove those internal states. No undocumented flag, transcript edit,
fabricated event, or compatibility fallback supplies missing evidence.

The result remains `support_claim: false` and `verdict: inconclusive` for
production support even when this bounded scenario is fully observed.
