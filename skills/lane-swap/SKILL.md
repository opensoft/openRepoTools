---
name: lane-swap
description: "Experimental external account swap with incomplete runtime integration; /lane-swap retains its historical unmanaged alias."
---

# Managed `/lane-swap`

Native/live support is experimental and `UNVERIFIED`. The approved behavior is
described by the source records
`openspec/changes/separate-swap-ctx-handoff/native-subagent-decision.md` and
`specs/001-separate-swap-ctx-handoff/contracts/managed-control.md`; those
feature records are not installed with this skill and may not be published.
The following external entry points exist, but their syntax and fake tests do
not establish native runtime support:

```sh
lane-swap <lane> --profile <profile>
# or
lane-managed swap <lane> --profile <profile>
```

Pass the current `--generation <generation>` for the enrolled owner and
retain request identity when reconciling an uncertain result.

In the current checkout these forms are experimental syntax only. Until the
selected runtime Gate 0 and native controller/daemon integration are proven,
managed swap must refuse before source interruption. Parser success, a fake
runtime, or a scaffolded entry point is not support and never permits a legacy
fallback or a second owner.

Require explicit managed enrollment and a known durable owner. One coordinator
owns native Agent/Task children. Track actual agent/task identities, parent
linkage, current invocation, and native lifecycle/tool events. Do not invent
per-child accounts, top-level UUIDs, SDK connections, mailboxes, or external
open/release operations.

A supported swap must fence admission, terminal-stop current native children
and tracked tools, prove durable worker-state clearing and old-writer/effect
exclusion, then restore the coordinator's exact native conversation
promptlessly under the explicitly selected authorized same-family profile.
The account/profile change does not change the configured model. Preserve
custom-agent definitions, model, effort, tools, permissions, workspace,
dirty/untracked work, and lineage claims. Swap requires no new model request,
generated summary, checkpoint, written handoff, commit, or push.

Do not declare `ready-held` from parent startup alone. The actual SDK-selected
runtime/version/mode must have a tested startup-orphan hold boundary. A returned
Agent launch tool does not prove its child finished; native background tasks
need current-run lifecycle/tool/effect evidence. Teams need separate capability
validation. Detached shell processes are external effects requiring exclusion;
parent exit or OS suspension alone does not prove them safe.

Before release, safely stopped unfinished children remain `resume-pending` for
a tested exact-continuation candidate or `restart-pending` for a new native
run. Keep completed children `completed`. Release is explicitly authorized
normal inference for the matching operation and generation:

```sh
lane-managed release <lane> --operation-id <operation-id> --generation <generation>
```

Only post-release correlated native events establish `exact-resumed` or
`restarted`. Correlate a new task with its coordinator, old task, restart
attempt, current invocation, retained definition, permissions, and tool/process
facts. `accepted-send` proves only delivery acceptance. Model-assisted restart
uses existing native records and coordinator context without a written handoff
or generated checkpoint, and reports model use separately from account
control. A restarted task does not prove old conversation or identity
preservation. Missing or contradictory evidence remains `unresolved`; keep the
lane held/indeterminate when safety is unknown and never replay uncertain
sends/effects or duplicate writers.

`/lane-swap` or `/swap` is token-free only when the frontend demonstrably
intercepts it before model dispatch. Otherwise tell the operator to run the
external command; do not invoke the historical handoff procedure as a silent fallback.
`lane-swap` remains Bash 3.2-compatible and treats a literal lane named
`swap` as data.

Managed `ctx` in `commands/ctx.md` has approved hold/restart policies for a
fresh coordinator under the current account, using a caller-supplied checkpoint.
The public wire accepts both `--workers hold` and `--workers restart`, and the
parser accepts those same values; current native integration refuses the
restart lifecycle until native restart admission and lineage transfer are
implemented and correlated. Wire
acceptance does not claim lifecycle support, and the superseded mapping path is
not a native fallback.
Managed `lane-managed handoff <lane> --checkpoint <checkpoint>` records only
the caller's reference and has no lifecycle effects. Never invoke it during
swap or worker restart.

`shutdown` must retain the durable managed owner, control service/endpoint,
and claims. Only explicit `unenroll` may remove ownership after authoritative
coordinator/child/tool quiescence and detached-effect resolution. Unsupported
setup-token profiles, missing exact-parent or safety evidence, and ambiguous
ownership refuse. Live validation requires separate authorization; a scaffold
or passing fake-runtime test never upgrades `UNVERIFIED` to supported.

## Historical unmanaged compatibility

On a lane without durable managed ownership, `/lane-swap` and `/swap` retain
their historical, operational aliases of `/handoff`. The legacy skill remains
the executable source of that procedure for existing records. Legacy `lane`,
`lane-start`, and handoff surfaces refuse a managed-owned lane rather than
starting a second owner.
