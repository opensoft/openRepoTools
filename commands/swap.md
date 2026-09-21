---
name: "Swap"
description: "Experimental native-lineage account swap with incomplete runtime integration; historical /swap alias for unmanaged lanes"
category: Lane
tags: [lane, swap, handoff, ctx, managed]
---

## Managed lanes (opt in explicitly)

Native/live support is experimental and `UNVERIFIED`. The commands below are
transport syntax, not evidence that the native runtime integration or its
startup-orphan gate has passed. The approved behavior is defined in the source
records `openspec/changes/separate-swap-ctx-handoff/native-subagent-decision.md`
and `specs/001-separate-swap-ctx-handoff/contracts/managed-control.md`; those
feature records are not installed with this command and may not be published.
For an explicitly enrolled lane, the eventual external account-control entry
points are:

```sh
lane-swap <lane> --profile <profile>
# equivalent operation surface:
lane-managed swap <lane> --profile <profile>
```

In the current checkout these are experimental forms only. Until the selected
runtime Gate 0 and the native controller/daemon integration are proven, a
managed swap must refuse before source interruption and preserve the owner,
claims, and unresolved effects for recovery. It must never silently use the
legacy handoff procedure or another owner.

Pass the current `--generation <generation>` when addressing an enrolled
owner; keep request identity stable when reconciling an uncertain result.

The approved architecture has one coordinator with native Agent/Task children.
Children are tracked by actual native identities and current-run events under
that coordinator; they have no separate account, top-level session, or external
open/release operation. Swap must fence admission, terminal-stop current
children and tools, prove durable worker-state clearing and old-writer
exclusion, then restore the exact parent conversation under the explicitly
selected authorized same-family profile. Unknown stop, identity, ownership, or
external-effect evidence keeps the lane held or indeterminate.

The control phase must make zero new model requests and generate no summary,
checkpoint, written handoff, commit, or push. A profile/account change does not
change the configured model. Preserve model, effort, tools,
permissions, custom-agent definitions, workspace, dirty/untracked work, and
lineage claims. Parent startup alone does not prove the children held: the
exact SDK-selected runtime must pass its startup-orphan gate before use.

At `ready-held`, safely stopped unfinished children are `resume-pending` for a
tested exact-continuation candidate or `restart-pending` for an approved new
run. Explicit release of the matching operation and generation is the inference
boundary:

```sh
lane-managed release <lane> --operation-id <operation-id> --generation <generation>
```

Only post-release correlated native events prove `exact-resumed` or
`restarted`. A new task must correlate to the coordinator, old task, restart
attempt, current invocation, and retained definition/permissions; send
acceptance alone proves neither result. Model-assisted restart uses existing
native task records and coordinator context, writes no handoff, and reports
its model use separately from account control. It does not prove preservation
of the child's old conversation or identity. Completed children stay
`completed`; uncertainty stays `unresolved`, with no duplicate writers or
replay of uncertain effects.

`lane-swap` is the thin Bash 3.2-compatible primary. A canonical lane named
`swap` is data, not a subcommand. A slash `/swap` is token-free only when the
frontend proves interception before model dispatch; otherwise use the external
command. There is no silent fallback to handoff, ctx, legacy launch, or a
coordinator-only restart.

Native background children need their own tracked lifecycle and tool/effect
evidence; return of the launching Agent tool is not completion. Unmanaged
detached processes need separate exclusion evidence. Native teams require
separate validation and are not covered by an Agent/Task capability claim.

Managed `ctx` has distinct hold/restart policies whose native integration is
still planned; see `commands/ctx.md`. Managed `handoff` in
`commands/handoff.md` records only a caller-supplied checkpoint. `shutdown` must retain the managed owner, control
service/endpoint, and claims; only explicit `unenroll` may remove ownership
after authoritative participant/tool quiescence and effect resolution.
Missing runtime evidence, unsupported profiles, or ambiguous ownership must
refuse, never fall back. Fake tests and scaffolded entry points do not verify
live account switching; live validation requires separate authorization.

## Unmanaged legacy compatibility

Without durable managed ownership, `/swap` remains the historical alias of
`/handoff`; invoke the `handoff` skill for that legacy procedure. The alias is
kept for existing unmanaged lanes and records, but it does not provide the
managed zero-model guarantee. Legacy `lane`, `lane-start`, and
`lane-handoff`/`/handoff` refuse a managed-owned lane rather than taking a
second owner.
