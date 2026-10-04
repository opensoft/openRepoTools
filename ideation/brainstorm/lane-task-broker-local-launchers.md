# Local Claude Launch Stack — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Keep pclaude as a direct profile launch, add oclaude for local Omnigent, and make lclaude enter a lane through oclaude.
Topics: lane-task-broker, local-claude-launchers, lane-session-operations, omnigent-adapter
Repository context: workBenches launcher ownership; openRepoTools LS admission and custody; Omnigent local session transport
Captured: 2026-10-04

## Possible feats

- **Three explicit entry points** — Reuse profile launch mechanics across direct, Omnigent and lane sessions with explicit lane admission.
- **Local session observation adapter** — Join communication and usage events to the exact native parent and lane generation.

## Focus

Brett selects local Omnigent for lane communication while keeping a direct
profile launch available. This amends the October 3 optional-local-Omnigent
direction. The [launcher contract](../../specs/001-separate-swap-ctx-handoff/contracts/claude-lane-launchers.md)
governs the selected design; this packet remains non-normative rationale.

## Selected model

| Entry | Route | Lane |
| --- | --- | --- |
| `pclaude <profile>` | Selected profile → native Claude | None |
| `oclaude <profile>` | Local Omnigent native-Claude adapter → same profile launch primitive | None by default |
| `lclaude <profile>` | Existing lane admission/LS → `oclaude` with explicit binding → native Claude | Required and admitted |

`oclaude` can serve both lane and non-lane sessions; `lclaude` supplies the
validated lane context. Omnigent is required for this Claude lane stack, and
uses the profile launch primitive. This is not a dependency on `pclaude` for
every other Omnigent harness. Existing wrappers do not yet implement the route.

## Interfaces and boundaries

workBenches keeps profile/account/binary selection and installs the wrappers.
LS admits the lane, retains local JSON authority and owns swap/control fences.
Omnigent supplies local session communication and observation transport.
The actual CLI must remain a custodian-owned child with the same exit witness;
the shared server, runner and container survive account transfer.

A source input fence must cover API/web messages and queued runner input along
with the keyboard. Preserve native transcript location/resume, tool policy and
hooks. Profile settings are supplied per runtime rather than inherited from
a shared daemon. These joins and controls need measured adapter integration.

Reuse native account usage snapshots alongside Omnigent session/child usage.
Preserve observation freshness and reset windows; token/cost estimates cannot
replace account limit observations. Local sessions need no codeXfactory;
factory broker delegation retains authenticated codeXfactory admission.
The deferred private worker adapter remains a separate capability.

## Alternatives and tensions

The earlier optional Omnigent lane transport offered a smaller dependency set.
The selected required local transport gives one lane communication interface,
with an additional adapter/install qualification obligation. Keeping `pclaude`
direct preserves an explicit profile-only entry. Native child mirrors may aid
observation without establishing that LS can interrupt those children directly.

## Open questions

Pin the adapter build and qualify per-child profile propagation, custodian-owned
launch, all-channel input fencing and native-history fidelity. Define wrapper
arguments and installation together in workBenches rather than inventing a
second profile resolver. T063–T065 are the governed implementation handoff.

## Relationships

- [Access and packaging](lane-task-broker-access-and-packaging.md) keeps factory admission and future private delegation separate.
- [Omnigent adapter](lane-task-broker-omnigent-adapter.md) records available primitives and qualification gaps.
- [Two-mode synthesis](lane-task-broker-synthesis-two-modes.md) joins local session communication with parent and worker ownership.
