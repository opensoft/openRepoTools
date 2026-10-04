# Claude profile, Omnigent and lane launchers

Status: accepted October 4 direction; implementation and runtime qualification pending

## Command responsibilities

Brett selects this Claude launch stack for local lanes. Broker delegation
continues to require codeXfactory admission. This amends the October 3 choice
that ordinary managed lanes could launch without Omnigent; historical records
and existing runtime evidence retain their original meaning.

| Command | Responsibility | Lane behavior |
| --- | --- | --- |
| `pclaude <profile>` | Resolve the selected profile and pinned native Claude binary, then launch Claude directly. | No lane lookup, claim or inherited lane attachment. |
| `oclaude <profile>` | Start or attach through the qualified local Omnigent server/runner and its native-Claude adapter, using the same `pclaude` profile-launch primitive. | No lane by default; accepts an explicit validated lane binding supplied by the lane launcher/service. |
| `lclaude <profile>` | Resolve/admit the lane under the existing protocol and LS, then launch through `oclaude` with that binding. | Lane launch requires local Omnigent. |

The conceptual execution sequence is `lclaude → oclaude → Omnigent native-Claude
adapter → pclaude → Claude`. For a non-lane Omnigent session it starts at
`oclaude`; for a direct non-Omnigent session it starts at `pclaude`. These are
sequences/responsibilities, not a claim that `omni pclaude` is an existing CLI
command or that today's wrappers implement them.

The current workBenches `lclaude` executes `pclaude --with-lane`; its `pclaude`
also retains explicit compatibility lane flags. The selected migration moves
lane entry to `lclaude` and routes it through `oclaude`. Old explicit lane
forms must refuse with migration guidance rather than launch a lane outside
Omnigent. Plain `pclaude` and plain `oclaude` must not discover or attach a lane
from cwd, tmux names or inherited lane variables. Direct profile launches do
not acquire an LS lane claim.

## Ownership and launch qualification

workBenches owns the launcher scripts and their installation. Reuse its
profile resolution, native binary pin/current selection, profile hooks and
configuration; do not fork account selection into Omnigent. openRepoTools owns
LS lane admission, binding, swap ledger and process-custody integration.
Omnigent owns its session transport and qualified native-Claude adapter.

The adapter must launch the actual native CLI through the admitted per-session
custodian so it has the owned child handle, exact runtime identity, wait and
ECHILD witness. Long-lived shared Omnigent server/runner processes must sit
outside that per-CLI custody scope and remain running during swap. A tmux
terminal ending, an Omnigent session closing or a parent wrapper exiting is
not the native CLI exit witness. Measure the runner/custodian integration;
the installed Omnigent launch path does not already prove this boundary.

Supply profile/config/auth settings per actual child launch. A shared daemon's
inherited environment is not an account binding. Reuse a profile-only execution
path that avoids nested launcher/tmux recursion and duplicate lane admission.
Preserve native tool policy, hooks and status-line chaining. If local Omnigent
or its required adapter is unavailable/unqualified, refuse the lane launch
before native spawn; do not silently use direct `pclaude` as a lane fallback.

Local lanes need no codeXfactory or shared cloud service. A local Omnigent
communication/session layer supplies no shared-worker grant and does not enable
the deferred private worker-broker capability. Factory broker tasks still enter
LS → codeXfactory admission → existing Hermes/Omnigent worker dispatch.

## Communication and swap

Bind the Omnigent conversation, runner/terminal incarnation, native parent UUID,
profile/account reference, custodian runtime and lane/owner generation. Keep
these identity types distinct. LS addresses only the currently admitted
generation and journals requests/results with deduplication and delivery state.
Accepted messages, mirrored child records and session status are observations;
they do not establish command completion, native child addressability or exit.

Keep the existing verified idle-boundary seal and headless exit. Every input
path must honor the source fence, including Omnigent API/web/session messages
and runner queues as well as keyboard input. After sealing A, no queued or new
prompt may reach it. A new input before sealing invalidates the observed idle
boundary. Deliver permitted pending work to B only after release/readiness.
Measure these controls before depending on them; mid-turn forced recovery and
Agent admission fences remain outside first delivery.

Resume retains the sealed native-history pointer and exact parent. Record any
Omnigent/native resume mapping, and refuse an unqualified cold-history rebuild
or automatic runner restart that bypasses LS claims/release. Native unfinished
children still require fresh child IDs under B; communication records do not
resurrect them. Keep EGS commands independent of agent/session cancellation.

## Usage observations

Reuse workBenches' native status-line publisher for available account limit
percentages/reset windows, and Omnigent events/transcript observations for
session/child tokens, context and estimated cost. The installed bridge inspected
October 4 captures context and cost but does not forward subscription limit
fields. New adapter capabilities need pinned-build measurement.

Record account/profile scope separately from session context, observation
timestamp/source, window/reset identity and owner generation. Preserve each
available limit bucket; missing/stale values remain unknown. Aggregate account
activity across lanes without double-counting parent/child costs. Cost/token
estimates do not establish subscription allowance or guarantee a wrap-up turn.
LS owns the swap decision and existing clean/repair classification.

## Delivery

FR-047 and T063–T065 own the launcher/runtime amendment. Its local qualification
is required before activating the new lane launch path or claiming end-to-end
swap delivery. T054 custody work continues; T055–T057 integration/evidence must
use the qualified new stack. Factory broker T059–T062 remains a separate tranche.
This contract introduces no live canary, account move or service deployment.
