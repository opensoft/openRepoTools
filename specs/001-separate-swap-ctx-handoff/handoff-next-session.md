# Swap rebuild — implementation handoff

## Current checkpoint — October 3, 2026: accepted factory access and packaging

Shared CPC coding tasks from LS use codexFactory admission before existing
Hermes/Omnigent dispatch. Installing/cloning the factory is not a project/pool
grant. Brett agreed to a lightweight authenticated factory client that reuses
the same service without requiring a full local factory installation. LS
lifecycle-only swap remains independent of Omnigent and shared factory/cloud
services. Private Omnigent delegation for owner local/VPS workers is deferred
outside the first delivery, with no CPC permission or automatic fallback.
T059–T062 cover the factory client and admission integration; a future private
adapter would require separate scope and capability qualification.

Qualify the complete authenticated admission path: current hosted MCP tools are
inspect/verify, and internal Hermes job handlers do not themselves prove public
tenant/pool protection. Exact API and package layout remain implementation work.
Follow the [accepted contract scope](contracts/lane-task-broker.md#accepted-access-and-packaging-scope)
and [rationale](../../ideation/brainstorm/lane-task-broker-access-and-packaging.md).

## Current checkpoint — October 3, 2026: distributed deployment direction

Local CPC installation can be qualified first. Engineers enrolling spare
xFactory compute should connect outbound to a shared cloud/Azure LS gateway;
each site still runs local runtime custody/swap control and EGS. Omnigent owns
workload/account placement through its existing worker registry/dispatch rail.
Reuse host enrollment and transport; CPU permission and model account permission
are separate. Cloud coordination never replaces local JSON swap authority or
proves death from lost contact. Azure resource choice, local-controller packaging
and remote transport remain qualification work, with no deployment authorized.
Follow the [deployment boundary](contracts/lane-task-broker.md#deployment-direction-cloud-gateway-and-local-execution-control)
and T059–T062; T054–T057 remain unchanged. The CPC's declared WSL/Docker substrate
does not certify installed custody against native Windows workers.

## Current checkpoint — October 3, 2026: parent and worker lifecycle split

LS owns main-parent A→B swap and stable factory-task attachments/results.
Omnigent's existing worker-management layer owns worker workload, authorized
placement, allowance admission and qualified worker recovery. Independent
workers continue during parent handoff; fence stale A requests, buffer results
and hand B task references/delivery watermarks without redispatch. Worker
replacement remains internal under the same logical factory task ID. Remote
commands belong to the worker execution site's EGS and require qualified site/
supervisor/incarnation/job references; A's local PID/EGS proves no remote exit.

Inspection found session creation, interrupt/history/resume and subprocess
lifecycle primitives, but no complete safe worker account-transfer controller
or subscription-allowance selector. Existing capacity checks and one-shot patch
results do not supply those guarantees. Extend the owning worker components;
sharing qualified swap/custody machinery is an option, not a new component
ruling. Follow the [findings](contracts/lane-task-broker.md#observed-lifecycle-support-and-missing-worker-swap)
and T059–T062. Prefer small tasks with estimated allowance plus reserve, while
retaining an exhaustion/refusal path. All runtime qualification is pending.

## Current checkpoint — October 3, 2026: reuse existing CPC factory workers

Brett directed LS broker integration to consume the existing CPC omniWorker
and codexFactory/openxFactory process. Follow the
[integration contract](contracts/lane-task-broker.md#existing-factory-worker-rail-is-the-first-adapter)
and amended T059–T062. Reuse factory job/run IDs, worker registry/profiles,
readiness, admitted dispatch and result enforcement. LS retains lane/task/
generation/parent-custody correlation; factory governance retains scope/workflow
authority. The current CPC patch worker is one-shot with no session persistence;
coder/worktree profiles are declared, not a measured resumable-worker proof.
Current clearing has not admitted `coding`; do not create a direct bypass.
Latest inspected execution-lane run failed in prepare before dispatch. No CPC
health, auth, interruption, EGS persistence or account transfer was exercised.

## Current checkpoint — October 3, 2026: swap and broker modes

Brett selected retaining ordinary lane swap plus explicit broker mode. Main
agents perform primary orchestration and delegate through LS; Omnigent chooses
authorized account/model/harness/host/container and LS collects results. Workers
may be remote and have separate actual session identities. Worker-account
replacement can leave the main agent live; main-agent swap remains available.

Follow the [broker contract](contracts/lane-task-broker.md), FR-046 and separate
T059–T062 tranche. Keep current native swap policy and T054–T057 gates intact.
Enforce broker delegation through LS, preserve EGS jobs and require execution-
site custody/effect proof; a network timeout cannot authorize duplicate work.
Omnigent dispatch/inbox code was inspected and the CLI reports `0.1.1`; model
routing, remote launch and policy behavior still need a pinned capability
matrix. No adapter upgrade, remote provisioning or live launch was performed.

## Current checkpoint — October 3, 2026: preferred task assignment default

Brett agreed on one Speckit task per implementation child run as the preferred
default. Several children may share a task with explicit roles/file boundaries;
bounded exceptions retain their task IDs and reasons. It is not a swap gate.
The [assignment contract](contracts/claude-cli-supervised-jobs.md#speckit-task-assignment-and-recovery),
FR-045 and data model define continuous assignment/runtime/file/job/evidence
joins. T055 owns the records/review groups and T056 their offline cases.

Review tasks with unverified contributions or outstanding jobs, including
recently returned children, plus parent edits and unmatched work. B verifies
acceptance and continues existing work with fresh children while preserving
verified completion and EGS jobs. Task grouping supplies no exit/effect proof;
forced recovery remains separately gated. The [rationale packet](../../ideation/brainstorm/speckit-task-recovery-overview.md)
captures tradeoffs. Documentation does not establish installed enforcement or
change T054–T057's open status.

## Current checkpoint — October 3, 2026: worktree inventory integration

Brett requested incorporating PR #97's useful worktree inventory into this
existing proposal. Follow the [inventory contract](contracts/claude-cli-supervised-jobs.md#worktree-inventory-integration)
and FR-044. T055 owns the service observation adapter and T056 its fault matrix;
no separate feature or executable OpenSpec checklist is introduced.

The managed JSON ledger remains the sole lifecycle/readiness authority.
Explicitly bound PR #97 sidecars may supply historical diagnostics, never
managed state or operation/generation counters. Refresh bounded, versioned
observations after source exit and before release; preserve read failures,
publication uncertainty, collisions/aliases and continuing-job caveats.
Required identity/writer/effect gaps block B with claims retained. Independently
safe diagnostic gaps become repair items; never automatically repair user
worktrees or request a final A response. T054–T057 remain open. This is a
documentation amendment, not implementation evidence, a PR #97 merge/closure,
or new canary/deployment authorization.

## Current checkpoint — October 2, 2026

Brett's source token requirement is recorded in the
[decision](../../openspec/changes/separate-swap-ctx-handoff/claude-cli-supervised-jobs-decision.md)
and [contract](contracts/claude-cli-supervised-jobs.md). Native wrap-up cannot
be the shutdown budget. The service must reconstruct state from durable
records without source tokens or a final AI handoff. Optional Stop-hook wrap-up
is attempted only before known exhaustion, never retried after exhaustion,
and never a readiness condition. The verified idle boundary, exact CLI exit,
descendant drain and effect reconciliation remain mandatory. Otherwise retain
claims and keep B absent; forced recovery remains out of scope.

The follow-up adds a sealed JSON-ledger `handoff.outcome` of `clean` or
`repair-required`, with exact transfer binding, reasons, evidence and repair
items. Deliver it before B's first turn. Clean needs a verified pre-exhaustion
checkpoint; incomplete/exhausted transfers require startup repair after source
safety is proven. B completes required repair before normal work. Persist its
completion separately without changing the original outcome. Both paths retain
the same exit/ownership proof, and user files or continuing jobs are preserved.

Continue T054 custody/idle-exit measurement, then T055's direct usage watcher,
continuous native child/task records and service-authored transition packet.
T056 must cover no allowance and no final handoff, interrupted wrap-up, child
usage failures and both proven readiness and bounded refusal. The
[verification record](verification.md) preserves the read-only ordinary-lane
observation separately from provider qualification. T054–T057 remain open;
T058 remains non-gating. This checkpoint adds no canary, seat-move, merge or
deployment authorization.

## Current checkpoint — September 30, 2026

The September 30 [decision record](../../openspec/changes/separate-swap-ctx-handoff/claude-cli-supervised-jobs-decision.md),
[capability contract](contracts/claude-cli-supervised-jobs.md),
[deployment plan](deployment-plan.md), and [tasks](tasks.md) supersede older
canary and deployment instructions below. This checkpoint authorizes neither a
canary run, an account seat move, a merge nor deployment. T054–T057 remain open;
T058 is a separate, non-gating derived-index task. The operative canary pair is
selected and recorded only when a future canary is authorized; `team05d` and
`team05j` are an expectation, not a binding.

The selected runtime is one CLI per lane in a shared container. Only the parent
conversation resumes. Safely unfinished children must be recreated with new
IDs; persistent execution-group jobs keep their IDs. Native Edit, Write and
NotebookEdit are allowed. Long-running and external commands use the lane MCP
bridge, lanes service and execution-group supervisor. The local JSON ledger is
the sole swap authority. QA Postgres, or SQLite when no database URL is set,
is a derived index that never gates a swap. First-delivery roster sealing waits
for the verified idle boundary after any Stop-hook wrap-up continuation; the
mid-turn Agent fence belongs to a future gate.

Commits `37bc05d` (custody checkpoint), `57973a2` (decision packet),
`3cf67b5` (dormant Docker preservation), and `5536710` (native editing policy)
are on branch `001-separate-swap-ctx-handoff`. The remaining T054/T055 code
and tests in this worktree are still in progress. Do not treat historical
private installs or attempted canaries below as evidence for this selected
provider or as authorization to repeat them.

## Current checkpoint — September 28, 13:23 UTC

The user requested a new-session handoff. Read this file, `AGENTS.md`,
`verification.md`, and the fresh attempt's `canary-plan.json` and `RUNBOOK.md`
before acting. This checkpoint does **not** authorize launch: the fresh attempt
is prepared but neither registered nor started, and its plan explicitly has
`live_execution_allowed: false`. Preserve the older failed attempt and all
evidence; do not replay its blocked prompt or change classifier safeguards.

Use Codex Luna Max to drive the run and Claude Sonnet for the canary, as the
user requested. The Speckit team roles in `AGENTS.md` still apply. A new source
candidate now accepts `lane-managed-cli start --model sonnet` and carries the
requested alias through strict v2 manifests, source intent, target creation or
reuse, and release. This is source-only work: the effective provider model is
unobserved, the candidate is unqualified and uninstalled, and the earlier
privately installed v8 remains unactivated. Focused canonical tests passed
9/9 for model binding and 40/40 for consuming control/source/vertical/route;
`verification.md` records the exact selectors. No new full census or live
canary ran. The old v7 full census remains red (2,746 passed, 14 failed);
Native13 and T054–T057 remain open.

The new distinct preparation lives under
`${XDG_STATE_HOME:-$HOME/.local/state}/openRepoTools/deployment-evidence/shared-session-resume-20260926T235017Z/attempt-fresh-20260927T215957Z/`.
Its lane is `swap-canary-20260927t215957z`, parent
`b7413633-87b6-4779-ae8b-e4d43734c316`, with separate nonce, workspace,
job IDs and barrier. The `candidate_id` in that plan points to historical
installed v8; it is **not** the new Sonnet-binding source candidate. The
previous failed evidence remains in sibling `attempt-v7/`, including the
classifier interruption, partial child with zero tool calls, empty job ledger,
and A/C exits. Sonnet's prior assessment was text-only; no authenticated
Sonnet canary or persistent job has been demonstrated. The provider report
draft is unsubmitted. The published old canary row remains PAUSED.

Next session: inspect current source and host state; qualify and freeze the
Sonnet-binding candidate with the canonical test wrapper and exact expected
Native13 accounting; perform a separate private install only after that gate;
then recheck real profiles/history/holders and publish/read back the new lane
canonically. Before dispatching any task, establish the **effective** Sonnet
model through supported provider evidence. If it differs, is unknown, or a
classifier interrupts again, retain evidence and stop. A distinct live canary
may proceed only once its own preparation gates are satisfied. Do not infer an
admitted job from `ownership-conflict`: the prior parent made that error.
Keep team05d as the last confirmed seat; no seat change is needed now. A move
to team05j is only for the operator after verified source exit/full ECHILD
and durable readiness, before target release. The full same-child job and
unrelated authenticated session continuity proof are still outstanding.

## Installed v8; live canary interrupted; cleanup complete — September 27, 19:28 UTC

Candidate `swap-001-20260927-45f3f22dff08` is privately installed and verified,
NOT activated. 153-file freeze SHA-256:
45f3f22dff08c90ce7ed8b9ecc324629f13e9b338fef01595577a85e6a4821fa.
Only tests/test_lane_managed_daemon_rollover.py changed after red full v7:
the fixture now uses the verified on_ready callback, preserving every behavior
assertion. Complete rollover12 and hygiene183 passed; JUnit SHA-256
205aa2739255af60fc40cd23831270000505afb022e88fa8015a6c62e6c59fa2.
Astra approved fixture-only composite qualification and root independently
verified the sole delta. Full v7 remains 2,746 passed /14 failed; do not call
it green. Native13 are unchanged and open. Installation verified43 files,
two hooks, all48 checked ambient paths unchanged and private imports.

Distinct lane `swap-canary-20260927-v7` was canonically published and started
once with parent67229fc9-a472-411c-b283-ee39739fc55e, runtime
8d3e0a72-bb83-4aac-bcaf-451411112a19, source team05d/targetteam05j.
One source prompt was sent. Native Agent toolu_01THaqf7uuat35CuEH1hecST was
interrupted by Claude's safety classifier; the CLI automatically fell back
from Opus5.5 to4.8. Root did not select fallback, resend, replay or bypass.
Partial child a4830bdb39663cb31 has8 transcript records and zero tool calls.
The parent tried one read-only job_status, received ownership-conflict, then
completed an authenticated Stop summary with1 hook/no errors. Its inference
that a job existed was incorrect: ledger jobs/operations, runner files and
job-domain records are all empty; no job-launch marker or release barrier.
This attempt is FAIL before admitted-job continuity and swap preparation.

A exited by the exact owned idle /exit, code0, full ECHILD/drained, no new
assistant model message during cleanup. Independent C run
e5b73dad-45e4-4a0f-b751-b5dfeaa1fefa survived A exit with its exact identity,
then exited code0 through its run-bound sentinel. Shared container identity,
start time and restart count are unchanged. No active test/probe/Claude A/B/C
remains for this attempt. Preserve its supervisor/state/evidence; no new
attempt or task replay around the classifier. Canonical row is published
PAUSED with this result. Seat remains last confirmed team05d; no seat move
was requested or performed. Team05j has not launched.

Evidence is under the current host-local root's attempt-v7 directory:
canary-final-disposition.json, failed-native-child/, canary-A-cleanup-result.json,
canary-C-final.json; installation/composite evidence are at the parent root.
The earlier failed v6 job remains terminal at its original domain deadline;
its reservation and supervisor are retained, never manually cleared. The live
authenticated same-child/admitted-job swap proof, Native13, T054–T057 and
all general rollout gates remain open. Latest user seat question was answered:
keep team05d; no move is needed while the live proof is blocked.

## V7 census complete; one fixture race under correction — September 27

Full canonical v7 census finished: 2,746 passed / 14 failed / 0 skipped /
0 errors, 2,760 cases in 3,725.84 seconds. Exact expected coverage is complete;
all 153 frozen hashes/modes are unchanged. JUnit SHA-256:
60ebd6e4db3f241171224e96989e5b4d15a8ec0b6a30f6b54bb6d78aa278ea83.
Native13 names/reasons match exactly. The additional failure is
`test_public_socket_real_state_retains_busy_a_then_delivers_b_c_once` at its
initial public-start: the client correctly refused a socket not yet owner-only.
The fixture waited for pathname existence, which can precede bind→chmod0600→
listen→verification completion. Production exposes an on_ready callback after
all those steps. Astra confirmed this race; Sol owns fixture correction and
exclusive focused test slot. No v7 private install or live canary occurred.

Retain the red full census and its unqualified analysis. Astra confirmed the
existing staged policy permits a reviewed fixture-only correction plus complete
consuming/hygiene confirmation with unchanged production/dependency bytes; this
must be separately recorded, never called a green full suite or a waived extra
failure. Production changes or unexplained failures require reassessment.
Root will freeze the corrected inventory and verify its evidence before any
private installation. The distinct next canary stays unregistered/unstarted.
Native13, T054–T057 and global rollout remain open. Seat stays team05d, target
team05j; no move is needed for automated tests. Actual source exclusion and
durable readiness must precede the operator seat-move request.

## V7 full census active; v6 job terminal — September 27, 18:51 UTC

Canonical v7 full census remains running: exec63753, wrapper2924270,
pytest2971479. Source/tests are frozen; observe this existing run. It is in
its long shell integration case, not queued now. No v7 installation or live
canary has been dispatched. The distinct attempt-v7 runbook and read-only
snapshot helper are prepared. Exact full coverage/failure mapping/no drift
still gate installation. Native13 and T054–T057 remain open.

The failed v6 original job reached the execution domain's existing one-hour
limit. The integrity-validated terminal witness records exit -9 and
subtree_empty=true, untruncated output, and before/after local-worktree
inventories. The command PID2667795 is absent; worker2667779 is an exited
zombie awaiting supervisor reap. This was the existing domain deadline, not
an operator cancellation or signal. Last heartbeat718; no script timeout or
success marker, no result file, and no release barrier. Preserve supervisor,
ledger/reservation and evidence; do not clear reservations manually or replay.
No successful swap, B observation or result consumption is claimed.
Evidence: canary-job-terminal-v6.json, canary-v6-job-terminal/; terminal record
SHA-256 7c072ebef78d73d113e60c3158035e2848a33f828e6adf3ef8ce4682944f5898.
A and C remain normally exited; shared container identity unchanged. Seat is
still team05d. The shared WIP checkout had no tracked changes before this
checkpoint; preserved untracked data remain intact.

## Frozen v7 census queued — September 27, 18:13 UTC

Sol's role-aware profile discovery correction passed 50 focused and 53
consuming tests. Read-only discovery against the deployed 418-config layout
and completed A transcript passed: no current holders, unknown holders or
ambiguity. Live-holder preservation is covered synthetically, not by that
zero-holder observation. Astra approved final static review. Strict OpenSpec
and both diff checks passed. Source/tests are frozen.

Candidate `swap-001-20260927-09217183d6c2`, 153-file manifest SHA-256
`09217183d6c21ffe1525c0d0b9b219806a3346586cdda0c1a161145e26e10bec`.
Only `lane_managed_profiles.py` and `tests/test_lane_managed_profiles.py`
changed from v6. Private v7 plan/inventory are prepared, NOT installed.
Root owns the sole feature test/probe slot. Canonical full wrapper PID2924270,
exec63753, launched at18:12:54 UTC and is queued behind external pytest
PID2896180 in another lane's openxFactory scratch checkout. Observe this
existing handle; never start a second census because the log is quiet.
`full-census-v7-run.json`, log, eventual JUnit and before/after manifests are
under the current host-local evidence root. Exact failure mapping/no drift
must qualify before copy; native13 remain open.

Failed v6 A/C remain gracefully exited. Preserve supervisor2634526 and its
original job worker2667779, actual command2667795 (start token ending26503128)
to its predeclared timeout; no barrier, replay or manual reservation clearing.
The current canary row was canonically published PAUSED with the refusal.
A future distinct canary is prepared but unregistered/unstarted under
`attempt-v7/`: lane `swap-canary-20260927-v7`, parent
`67229fc9-a472-411c-b283-ee39739fc55e`, nonce`04bb5dd7ab2fdf72ebe2dd80`,
new workspace/barrier and same bounded scripts. Bind terminal30x100, wait for
exact trust selection before separate Enter. No model/config/profile mutation
or runtime launch has occurred for v7. Seat remains team05d, targetteam05j;
operator move still requires actual source exclusion and durable readiness.

## V6 cleanup complete — September 27, 18:03 UTC

A exited through its owned idle `/exit`: code0, exact source reaped and
custodian `drained=true` (full ECHILD). This is failed-canary cleanup evidence,
not swap readiness. Original job PID2667779 with start token ending26503115
survived outside A's subtree, heartbeat102; C and container unchanged at that
checkpoint. C then exited normally through its run-bound sentinel, code0;
its manager and CLI are no longer live. No A/B/C CLI or live probe remains.

Preserve original supervisor PID2634526, job, ledger/reservation, both private
installed versions and all evidence. The job must reach its existing
3,600-second bound; do not create the barrier, relaunch it or manually clear
its reservation. Revalidate exact identity before any process action. No
swap operation, durable ready, target launch, seat move or activation occurred.
Astra approved this disposition. Root returned the sole focused test slot to
Sol for the discovery correction after Astra's traversal contract; read-only
actual deployed-layout discovery must qualify before another full census.
A subsequent canary must use distinct session/job/workspace scope; this failed
attempt cannot be replayed. Evidence: `canary-cleanup-v6.json`,
`canary-v6-cleanup-source-exited/`, `canary-C-final-v6.json`.

## V6 installed canary checkpoint — September 27, 18:01 UTC

The full canonical v6 census completed: **2,735 passed / 13 failed / 0 skipped**,
2,748 test cases. All thirteen failure names/reasons match the retained native
ctx/restoration requirements. All 153 frozen files remained unchanged. Coverage
normalizes only the single live-holder test's `os.getpid()` parameter; raw ID
differences are retained. JUnit SHA-256:
`f97d79d7c691805c037f77aa28e2c5b54ee358fb178453d4f3e4c898b75cc45a`.

Private `swap-001-20260927-75da487cfaa3` is installed and verified: 43 file
copies, two hooks, all 48 checked ambient paths unchanged, private import
resolution. It is NOT activated. Installed v5/v6 remain immutable.

Real A started once through the installed command, runtime
`e7ab1361-ade4-4eac-a7fe-fbd03d7dfd77`, parent
`38ce6d48-9543-4080-9660-c7e9c311aa0b`. One native Agent child
`a6e5eb77ea8c06edf` admitted original job
`canary-job-a81bd43dcf5516394f7e737c` once (PID2667779), read status/output and
returned. Actual authenticated Stop completed: one successful native Stop hook
summary plus integrity-valid custodian turn1 begin/event digests. Raw Stop
payload/ticket are not retained, so field predicates are validator-backed,
not independently replayable. Astra qualified this derived evidence.

**The one `/swap` refused before preparing an operation:**
`profile storage tree contains a symlinked config path`. The first encountered
path is the existing legacy `profiles/opensoft-max-brett-heap` alias; normal
shared commands/rules/skills/agents and state directories are also symlinks.
The discovery walk rejects every directory link except `projects`. No profile
links were changed. Ledger operations remain empty; no source exit, target
launch or seat move occurred. V6 canary is FAIL before swap preparation.

At this checkpoint A PID2635049, custodian PID2635007, original job PID2667779
and independent C PID2623355 (manager2623266) remain live. Attached terminal
exec44345 belongs to A. Never signal these numeric PIDs without checking their
recorded start identities. Root owns cleanup/evidence; Astra designs the
profile-discovery correction, Sol implements after direction. Do not restart
or hotpatch the existing v6 supervisor, replay the job, create its release
barrier, or start B. The job has its original 3,600-second bound. Seat team05d,
target team05j. Request movement only after a future valid source exit plus
durable readiness; this failed attempt has neither.

Retain two scoped limitations: default80-column trust selector redraw omitted
label text and failed closed; reattaching the SAME source at30x100 produced
full Yes selection, then separate Enter passed. Claude automatically fell back
from Opus5.5 to4.8 after the child returned. No task replay or manual fallback
was sent; no one-provider-request claim is made. Exact child tool correlation,
job launch intent/started records, heartbeat41→74 and unchanged C/container
witnesses are in the host-local `canary-v6-before-swap` and
`canary-v6-swap-refused` evidence. Native13, T054–T057 and general rollout remain
open. Earlier queued/running census text below is historical.

## Frozen v6 census — launched September 27 at 16:36 UTC

Astra approved the one-line production correction and installed-first-use
regression. Repository first-use tests passed 2; private installed executable
first-use passed 1; the combined control/vertical/installed scope passed 15.
Strict OpenSpec and both diff checks passed. The distinct C-v2 observer check
also passed without starting a CLI. Source and tests are frozen.

Frozen inventory: 153 files, SHA-256
`75da487cfaa3f9ca82cfdb28391fbfd343d5acf62221b0481c7cc44a72932470`.
Only `lane_managed_cli_control.py`, `tests/test_lane_managed_cli_vertical.py`
and `tests/test_lane_managed_cli_installed_route.py` differ from v5. Candidate
`swap-001-20260927-75da487cfaa3` has prepared private plan/inventory v6 and is
NOT installed. The new full canonical census must qualify it first.

Root owns the sole feature test/probe slot. The existing full wrapper PID is
992769, exec session 94463; its basetemp is recorded in the host-local run
JSON. The canonical wrapper acquired the slot at 16:53:55 UTC and its
pytest PID1193066 is live in this feature worktree. The previous external run
finished. Observe the existing handle and exact process identity; do not restart
on silence, a status file or an observation timeout. Private artifacts are
`full-census-v6-run.json`, `full-census-v6.log`, eventual `full-census-v6.xml`,
and frozen before/after manifests. Previous real C is terminal; no canary A/B
CLI or job has started. Seat remains team05d.


## Current checkpoint — WIP recovered; first-start defect under correction

The user approved the one-time shared-WIP reconciliation. Recovery
`cc320dc6b2bb7720d977a985e02f8b4c9a40900f` was pushed normally and verified
as an ancestor of fetched remote `ecf29f5955334241b7950acd9a4473ec8421b813`.
Both histories, all 53 published lane rows and all 610 untracked files were
preserved. The exact canary row is published and canonical readback passed.
The older dirty-file/rebase blockers below are resolved historical evidence.

Private v5 remains immutable and unactivated. Its first real public `start`
attempt failed before enrollment: start_supervisor's recursive mkdir created
new host/lane ancestors with mode 0755; the child correctly refused unsafe
state before creating an owner, credential, session intent or Claude runtime.
Read-only validation reproduced the exact refusal. No source/target Claude,
model turn, admitted job or seat move occurred; no blind retry was performed.
The proven-empty newly created scaffold was preserved by atomic rename into
owner-private `.git/openrepotools-recovery/swap-canary-v5-empty-eagle`, with
UID/device/inode/mode evidence. Existing state was neither chmodded nor deleted.

Independent C ran once, was observed idle with its exact identity throughout
the failed start, and exited normally on the run-bound /exit sentinel (code 0).
Its manager and CLI are no longer live. The shared py-bench identity, start
time and restart count remained unchanged. The startup observer's null-CLI
race is separately recorded; a distinct future witness script is prepared.
This closes the v5 live attempt as FAIL before source admission, not a swap PASS.

Sol is correcting canonical private-layout initialization and adding public
first-use/unsafe-preexisting regressions; Astra reviews. Sol owns focused
validation; root owns the next freeze, full canonical v6 census and scoped
installation. Changed production bytes require that new census; the earlier
fixture-only composite allowance cannot be reused. Native13 and T054–T057
remain open. Seat remains team05d, target team05j. Request the move only after
exact A exit and durable readiness on a subsequently gated candidate.

Artifacts under the current host-local evidence root: `wip-recovery-approved.json`,
`canary-registration-plan.json`, `canary-A-first-start-failure-v5.json`,
`canary-v5-scaffold-preservation.json` and `canary-C-final-v5.json`.


## September 27 resumed retry — shared history conflict

The tracked xFactory handoff is now committed and the original dirty-file
blocker is cleared. The installed 43-file copy and pinned CLI hash were
rechecked unchanged. Canonical `set-row-state` refreshed the existing canary
row in local commit `602af6b8fcb28bd222028fb58b9981ca716b21c8`, but publication
exited 3: rebase conflicts at older `openXfactory-2` commit `3f6e79fcd`.
The helper aborted; the shared checkout is clean and not mid-rebase.

Fetched origin/main `7382d82e6a362676915a9453656a5e23be7d023f` has no canary
row. The content comparison found 37 local plus patches across multiple lanes.
An isolated, unpublished merge assessment preserves both histories and exposes
four conflicted files: `lanes/LANES.md`, the openxfactory-4 handoff
`handoffs/xFactory/session-handoff-2026-09-04-lane-opendox.md`, the opsXfactory-1
handoff, and `lanes/log/opsXfactory-1.md`. Its merge remains unresolved only in
the private assessment copy, not the shared checkout. No reset, shared manual
rebase, shared conflict resolution or remote recovery push was performed.

The user was asked to identify the shared WIP reconciliation coordinator.
Reconciliation must preserve unpublished work and current published bindings;
then retry canonical publication of the existing canary row. Evidence is in
`canary-publication-retry-v5.log` and `wip-recovery-assessment-v5.json` under
the current host-local evidence root. No source, target, persistent job or C
has started. No seat move requested; source remains team05d, target team05j.


RESUMED by 01a0dfba-6436-76b3-9b6c-518c54a4abcb@Eagle (lane swap-rebuild-codex) at 2026-09-26T23:48:00Z — user explicitly resumed the September 26 checkpoint.

## Active resumed checkpoint — private v5 installed; publication blocked

The user resumed this goal; older PAUSED instructions below are historical.
The goal is active and waiting for a required external checkpoint, not complete.
Astra leads architecture; Sol implements. **No tests, probes, installer or
registration helper is currently running.** Old exec/PID records below are
historical; never signal them without fresh identity verification.

The tested private candidate `swap-001-20260927-7e4e6694a135` is installed and
verified, but not activated. Its version directory is under the current
host-local evidence root's `private-install/versions/`. All 43 copied files
and 2 hook entries match; no missing/extra files; all 48 checked ambient paths
are unchanged. Installed CLI help exposes `observe-target`, and all five
loaded managed modules resolve inside that private version.

Validation remains honestly split: complete v4 census **2,731 passed / 14
failed / 0 skipped**; thirteen exact native ctx/restoration failures remain
open. The other failure contained two T019 legacy fixture assertions. Sol's
reviewed one-line correction supplies actual TABs to fake tmux, preserving
positive attach/read/no-effect assertions. Complete legacy-wrapper + all
repository hygiene then passed **184 tests / 0 failures / 0 skips**, 2,561
deselected. V5 differs from v4 only in that shell fixture; all production,
installed, dependency and test-framework bytes are identical. Both 153-file
frozen after-checks show no drift. This is not a green full regression or T057
completion. Astra approved this joined evidence only for the staged scope.

The current inventory is `frozen-legacy-v5-before.json`, SHA-256
`7e4e6694a1350569a1f0db0e52296f1473cdf75ba7094af06b274c00b6e7f830`.
Final focused source/control/custody/installed-route validation passed 47 tests;
trusted and fresh-untrusted actual pinned CLI offline startup/owned-exit probes
passed normal exit0/ECHILD. They used fake auth and no model prompt; provider
attempts were not measured. Actual authenticated Stop/child continuation still
needs the installed canary. Read [verification.md](verification.md) for hashes
and scopes. Source/test/installer bytes remain frozen; preserve all other
preexisting dirty/untracked feature work and dormant Docker/scaffolding files.

**Blocking action:** canonical canary registration created local WIP commit
`05a8b084641833cd938c506cf1b16d3bedb0822f`, but all six push attempts were
non-fast-forward and the helper exited 3. Its rebase is blocked by another
lane's dirty `handoffs/xFactory/session-handoff-2026-09-05-lane-opsXfactory-1.md`.
The helper left that file unchanged. The user has been asked to have the owning
xFactory lane commit its handoff and report when done. Do not commit that file,
stash/reset, hand-rebase, or rewrite the workspace pointer to bypass this.

The exact local canary row is verified; it was not published by this attempt.
**Do not rerun add-row:** it already exists locally. After the owner checkpoints,
re-read state and use the canonical helper publication workflow, then verify
published identity before enrollment. A legitimate current `set-row-state`
update can publish the prepared state; a no-change `commit` may return without
pushing, so inspect the helper's actual result. Refusals are relayed, not bypassed.
The last local-ref observation was ahead 37 / behind 2,574 before this final
handoff checkpoint; do not repeat that count as a new network observation.

Private evidence root:
`${XDG_STATE_HOME:-$HOME/.local/state}/openRepoTools/deployment-evidence/shared-session-resume-20260926T235017Z`.
Use `private-install-plan-v5.json`, `private-install-inventory-v5.json`,
`private-install-verification-v5.json`, `installed-cli-resolution-v5.json`,
`canary-registration-plan.json`, the refusal log and `deployment-checkpoint-v5.json`.
V1-v4 plans are historical blocked preparation; do not install them.

Canary lane `swap-canary-20260926`, exact parent
`38ce6d48-9543-4080-9660-c7e9c311aa0b`; immutable job, second edit, prompts and
independent C helper remain prepared and unexecuted. No authenticated A/B,
admitted job or C has started. **Seat remains team05d; target team05j. Ask for
seat movement only after exact A exit and durable readiness, then wait for
explicit confirmation.** The shared container and unrelated sessions stay live.
After publication, follow the private canary runbook with the installed bin
and real runtime profile root/private two-profile manifest, not the empty
installer profile destination. Recheck retained hashes before live use.

Source uses the exact per-session subreaper; jobs survive outside A's subtree.
Optional Claude wrap-up occurs before control entry. Parent UserPromptSubmit
begins a model turn; pending fences cover lost callbacks; exact Stop settles.
Trust input is bounded to the measured chooser; local help/blank Enter are
intercepted. Release launches once and returns a pending locator;
`observe-target` observes/adopts that same launch, never respawns. No forced
source fallback or broad process kill. General rollout and T054–T057 remain open.

## PAUSED by user — 2026-09-26 21:36 UTC

The user requested: “we are out of tokens. so shut down gracefully and and make
handoff”. **Do not continue implementation or tests until the user resumes.**
This checkpoint supersedes the older next-step blocks below.

### State and authority

- Work in the existing feature worktree, branch
  `001-separate-swap-ctx-handoff`, HEAD
  `faebff5fe47a9cf1c10b4f5e41186dd782e8e90e` (verify actual HEAD on resume;
  no implementation commit was made during this checkpoint).
- Preserve every dirty/untracked file. No reset, stash, broad cleanup or
  `git add .`. In particular preserve `.scratch-l1-handoff/`, scaffolding,
  dormant Docker work, and all new shared-session modules/tests.
- User requires **Astra for architecture/thinking and Sol for implementation**.
  That later instruction governs this work over the older Luna writer role.
- User explicitly permitted host tests: “no dev container, use host tests”.
  Run the canonical `tests/run.sh`; select tests with `-k`, not positional
  file arguments, since the wrapper already selects `tests`.
  Coordinate one feature test run at a time. Its documented
  `--parallel-safe` mode is available for isolated focused runs.
- **Seat remains on team05d. Target will be team05j. Do not ask for the move
  yet.** No authenticated A/B session, admitted canary job, source/target
  account swap, live installation, implementation commit or feature push was
  performed in this checkpoint.
- The shared container and unrelated sessions must stay running. Source
  exclusion uses one per-session Linux subreaper custodian. L1 supervisor/jobs
  remain outside A's subtree. Never stop the shared container, use a broad
  process-group/user kill, or reintroduce the superseded host Docker broker.
- T054–T057 remain open. Governance permits a versioned opt-in deployment for
  the named canary only after its applicable gates pass. General rollout,
  feature completion and T057 still require their full gates. The thirteen
  native `ctx`/restoration acceptance requirements remain intact.

### Immediate blocker — resolve this first

The real `lanes-edit.sh workspace-root` returns the WIP repository.
`ManagedStateStore` therefore uses the WIP Git common directory.
`claim_lineage_workspace` requires that state common directory in the claim;
`ClaudeCliHistoryWitness._worktrees` compares the same field against the
actual project worktree's Git common directory. A valid separate project
(or the standalone canary fixture) consequently cannot become ready.

**A lane-row change does not by itself solve this:** the current helper takes
no lane argument and returns the global workspace root. Astra must settle
the distinction between the state repository and the registered project
repository/common directory; Sol then implements it consistently in
claims/history/control with a real cross-repository regression. Do not use a
fake `LANES_EDIT` helper, falsely label the WIP common directory as the
project's, or weaken the identity check just to pass the canary.

### Code on disk

New shared route:

- `lane-managed-cli`: start, attach, ready, release, status and private hook
  observation/control surfaces.
- `lane_managed_cli_control.py`: persistent supervisor composition,
  enrollment, prepare/reconcile/release and target adoption; still under test.
- `lane_managed_cli_source.py`: source/target custodians, parent registry,
  exact source closure, fenced input, observational hooks and target witness.
- `lane_managed_cli_runtime.py`: immutable per-runtime bundles, pinned Claude
  2.1.283, exact UUID and lane name, foreground-only policy, native
  Read/Glob/Grep/Agent only, admitted MCP execution/editing, scoped profiles,
  disabled updates and managed instructions.
- `lane_managed_cli_history.py`: bounded exact parent/linked-child transcript
  reads and registered worktree/reservation observations.
- `lane_managed_local_jobs.py`, `lane_managed_job_runner.py`,
  `lane_managed_supervised_jobs.py`: independent persistent Linux jobs,
  generation credentials, bounded output/results and local effect settlement.

The source profiles intentionally have `projects` symlinks to the same shared
history directory. The control draft's erroneous blanket symlink refusal was
fixed: validate/canonicalize the trusted configured shared store. Start now
requires explicit `--cwd`; never default it to the WIP state repository.

Late edits that **must be rechecked**:

1. Final target ownership check and fork under the same owner lock, graceful
   already-exited A handling, client-disconnect handling and release deadlines.
2. Exact B observation followed by adoption into the active generation,
   next-target UUID rotation and repeated swaps.
3. Source custodian continuously draining the PTY into a bounded 1 MiB buffer
   to prevent B startup backpressure. This last patch was not compiled/tested
   after application.
4. Stop/StopFailure evidence is bound to the parent, source runtime and turn/
   peer identity. Review the remaining cross-turn raw-event digest blacklist:
   identical legitimate responses can otherwise be refused.
5. The new control socket fixture's missing `listen(1)` was corrected after
   the last run; correction not yet rerun.

A model-free vertical integration test was assigned to Sol jobs writer:
`tests/test_lane_managed_cli_vertical.py`. It was interrupted by this pause;
inspect whether a partial file exists. It must exercise the real control,
ledger, custodian and job endpoint, faking only Claude/provider behavior.

Packaging in `openRepoTools`, README and installer/hygiene tests now lists
**31 bin files / 45 artifacts**, including 15 managed Python modules. Dormant
Docker authority modules are excluded. The private-root staging test is
written but unrun on the final candidate. Do not install from a changing tree.

### Exact evidence, without adding overlapping counts

- Latest combined feature gate: **42 passed, 1 failed, 2,668 deselected**.
  The sole failure was the new control test's missing socket `listen(1)`.
  Source/history/job/adversarial cases passed; this precedes the late patches.
- Controller/daemon canonical census: **310 passed, 0 failed**, 2,397
  deselected, 98.63 seconds. JUnit SHA-256:
  `7bd0928917af22a1df29f9d23604459b488d016d8368123e37d7760eb5368349`.
- Native cleanup/ctx census: **4 passed, 13 failed**, 2,687 deselected,
  64.57 seconds. All thirteen retained positive ctx/restoration tests stop at
  the existing public unsupported boundary. Latest owner-fence/unenroll and
  marker-normalization tests pass. JUnit SHA-256:
  `06f8c10a8911b92a35629bede385c70b6a70649850131738f3c6b742636fd1f6`.
- Offline pinned CLI PTY probe: one intercepted `/swap`, one forwarded
  `/exit\\r`, exit status 0, no signal, 801 ms, **zero fake API requests**.
  This is a normal-CLI offline baseline, not the installed managed path or an
  authenticated account test. Probe:
  `tests/probes/managed_cli_pty_swap_calibration.py`, SHA-256
  `0de08c7e7ab8f0576f21726435ac31913280d71acf8495a714bdba1a6bd9776d`.
- The two earlier custody fixture failures were diagnosed as PTY SIGHUP
  before descendant detachment. A real kernel reproduction returned
  descendant signal 1. Fixtures now use setsid/readiness handshakes with the
  original custody assertions preserved; the subsequent feature gate passed.
- The earlier installer 93-pass/2-failure run saw concurrent file edits.
  Later inventory additions and the staging test have not had a frozen rerun.
- Strict OpenSpec validation and diff checks passed before the final runtime
  edits. No frozen full-suite or deployed-canary acceptance result exists.

### Private evidence and prepared canary

Host-local evidence root (do not commit its contents):
`${XDG_STATE_HOME:-$HOME/.local/state}/openRepoTools/deployment-evidence/shared-session-20260926T210840Z`.

It contains private JUnit reports, PTY calibration, before-install ambient
hashes, `canary-preparation.json`, an initialized disposable
`canary-workspace`, and `canary_job.py`/`canary-job-plan.json`.
The job has not run. It writes a launch marker exclusively, waits on an
operator barrier for at most 3,600 seconds, then writes a nonce-bound result
exclusively, so duplicate launch is observable.

The source/target profile manifest was read-only at its global location.
A private immutable two-profile projection `claude-profiles.json` and
`provenance.json` live in this evidence root. The two explicitly authorized
profiles were configured as eligible there; this is **not paid-seat/auth
proof** and does not relax the global inactive-profile gate. No credentials
were copied and the global manifest was not changed. Pass this projection
only through the scoped `CLAUDE_PROFILES_MANIFEST` environment.

Proposed lane `swap-canary-20260926` has no row yet (confirmed absent).
Canonical helper reads identify Eagle/seam and the actual WIP workspace.
Do not manufacture workspace helper output for the live proof.
`canary_c_offline.py` may be present as a prepared private helper for an
independent real pinned CLI C using isolated fake auth/API; inspect its
checkpoint. No C launch was authorized as part of the shutdown.

### Resume order

1. Stamp the authoritative lane handoff RESUMED with the new session ID;
   inspect dirty files and live agents/processes before restarting writers.
2. Resolve the WIP-versus-project claim identity blocker with Astra.
3. Compile/review the late source/control changes; complete the model-free
   vertical test and focused regression gates with Sol.
4. Freeze source, rerun canonical installer/import/staging tests and the full
   regression census. Map failures exactly; no skip/xfail or assertion waiver.
5. Prepare a versioned private install with all three destinations scoped:
   `OPENREPOTOOLS_BIN_DIR`, `CLAUDE_PROFILES_HOME`, `CLAUDE_USER_DIR`.
   Leave HOME and global installs unchanged. Preserve claims/jobs on rollback.
6. Only after these gates, register the concrete canary correctly and start
   A under team05d. Draft API (compiled, not live-validated):
   `lane-managed-cli start <lane> --source-profile team05d --target-profile team05j --parent-uuid <uuid> --mode fresh --cwd <fixture>`.
   Attach its returned custodian, make a foreground child admit the test job,
   then use the owned `/swap` route and `ready <lane> <operation_id>`.
7. **Only when A is proven gone and ready-to-resume is durable**, tell Brett
   to move the seat from team05d to team05j. After his confirmation, explicit
   `release <lane> <operation_id>` must resume the exact parent once.
   Have B continue the saved child and consume the original job's result.
   Confirm C/shared container survive and no duplicate job/source request.
8. Record the installed result and limitations. T057/general rollout remain
   open until their own gates pass.

At pause the implementation lead reported no live feature pytest, control
service, source custodian or authenticated canary process. Preserve unrelated
sessions and tools. All writers were instructed to stop; inspect actual
agent/process state again on resume.


## Resume here: shared-container graceful-session plan — September 26

Brett clarified that many Claude CLI sessions share the running container and
it must stay running. Follow the [current delivery plan](deployment-plan.md)
and [contract](contracts/claude-cli-supervised-jobs.md). The dedicated Docker
provider is a dormant superseded candidate; preserve its code and evidence.
Do not require host Docker/cgroup access or move the supervisor to WSL. L1 and
jobs may remain inside the container with lifetimes independent of A.

T052 and T053 keep their recorded scope and evidence; T054–T057 remain open.
Next implement/validate the per-session launcher journal and owner/restart
fence, complete known foreground lifecycle observations, isolated immutable
config/auth paths and independent supervisor job integration. Current private
fixed MCP/settings paths must not be shared writable launch destinations.
Optional model wrap-up precedes control entry; a returned prompt is not CLI
exit. Unknown children, refused exit, lost journal or uncertain effects block B.
Forced per-session recovery requires a separate gate; never stop/kill/restart
the shared container or use broad user/shared-process-group kills.

The next planned fixture runs A and independent C in the SAME container. A
finishes foreground work with native-child history and exits naturally; a
supervisor-admitted job retains identity/output and C/container stay running.
After exact exit, fencing and history/job/effect reconciliation, explicit
release starts B on A's exact parent once. Cover uncertain exit, duplicate
targets, stale A actions and launcher restart. Context restoration is not
model-task completion; completed children/jobs are not repeated.

The later explicit user instruction authorizes completing implementation,
validation and deployment, with Astra thinking and Sol implementing. Use the
[Linux subreaper provider contract](contracts/linux-session-subreaper.md).
Keep extensive dirty/untracked work intact. Record a concrete named canary;
account seat changes remain user-operated. Historical document-only limits do
not block the newly authorized work.
Public support remains disabled and existing suite failures/Bite evidence
remain as recorded. The historical checkpoints below are not current action
instructions.

## Historical September 25–26 dedicated-container candidate checkpoints

All directions in this historical section describe the superseded dedicated
Docker candidate. Its code and evidence are retained, but its host-service
questions and forced-stop plan are not current prerequisites or instructions.
The current plan is the shared-container section above.

### September 26 Sol implementation checkpoint

The private code now includes `lane_managed_host_docker.py` (bounded local
Docker HTTP transport and fresh resolved-config checks),
`lane_managed_host_broker.py` (append-once source/job cgroup allocation and
retained-FD custody candidate), `lane_managed_host_preflight.py` (read-only
host facts), and `lane_managed_job_runner.py` (T053 one-shot launch intent,
private bounded output/result custody, subtree-drain refusal and witness
adapter). The runner takes an injected trusted OS domain; it has no concrete
host-cgroup process backend. The focused canonical selector for the runner,
source provider, Engine adapter and T053 ledger passed **44 tests**, with
2,595 deselected. This is offline foundation evidence, not a production
T054 exclusion or persistent job.

The read-only preflight reports cgroup-v2 mount writable=false, Docker socket
peer PID visible=false, Engine 29.6.2/cgroupfs/v2, and
host_broker_candidate=false. A disposable host-namespace helper still could
not authenticate the Docker socket's daemon PID or read the required host
namespace identity. The next required operator input is where Docker Engine
actually runs and what host service boundary can retain cgroup FDs and
authenticate the daemon. Do not weaken the attestor or recreate a named
parent to manufacture continuity. Authenticated host IPC, concrete job-cgroup
backend, waiting entrypoint release, admitted Engine exec and the MCP/CLI
supervisor bridge remain unimplemented. T054–T057 remain unchecked.

An isolated Claude 2.1.283 fixture with fake key and loopback API tested a
candidate `/swap` interception. `--restricted` ignored the fixture's
user/project custom commands. A local plugin supplied explicitly by
`--plugin-dir` loaded a namespaced command: typing `/swap` selected
`/swap:swap`. A `UserPromptExpansion` matcher for `swap` missed and the fake
API counted eight requests; matching `swap:swap` blocked expansion with zero
fake requests and no remaining CLI process. Its event reports the normalized
prompt, not the original keystrokes. This proves one bounded CLI mechanism,
not an installed authenticated route, crash/timeout behavior or exhausted
quota support. Preserve the external local control fallback. The exact
artifact hashes and limits are in `verification.md`.

For the current execution order, use the reviewed
[completion and deployment plan](deployment-plan.md#current-delivery-plan-claude-cli-supervised-jobs-v1-september-26).
It schedules the T055 minimal job runner alongside T054 so containment is
tested with a truly admitted job, separates offline/OS/Claude acceptance,
and keeps the seat move at the installed T057 canary. T054–T057 remain open.

September 26 continuation: the operator chose foreground-only native Claude
work for the initial managed capability. The private
`lane_managed_claude_launch.py` builds and validates a pinned Claude 2.1.283
exact-parent `--restricted` launch: file tools plus foreground `Agent`, no
Bash/PowerShell, explicit denies, one strict MCP config, pinned settings,
and both documented background-disable environment variables set to `1`.
`lane_managed_docker_source.py` now requires that launch policy in its
container configuration and rejects a resume parent different from the
source claim before an Engine mutation. The focused `tests/run.sh` gate
passed 21 tests, 2,595 deselected; OpenSpec strict validation passed. This
is policy admission against fakes, not effective-runtime attestation. The
actual MCP job broker, all-path CLI launcher, production host cgroup witness,
integrated supervisor route, canary and installation remain unimplemented.
Do not mark T054–T057 complete or enable the public managed capability.

The next T054 read-only witness slice now binds the retained cgroup FD through
its mount ID and cgroup-v2 mount record to one source path. A separate retained
job domain checks admitted root PID/start-token membership. Twenty-five
focused tests pass; strict OpenSpec validation and syntax checks pass. Host
preflight found Docker Engine 29.6.2 with cgroup v2/cgroupfs, while this
process's cgroup mount is read-only. A disposable, model-free BusyBox
container was started and removed; Docker's reported host PID was invisible
to the current process. This session is in a container connected to the
Docker socket, not the Engine host PID namespace. No account seat was moved.
Source admission refuses a missing trusted Engine-host attestation before any
Engine mutation; the candidate probe cannot self-attest. The remaining
production gap is a trusted Engine-host
broker/attestation, provisioned source and job cgroup domains, full restart
fence coverage, and an integrated detached-writer runtime proof. Positive
exclusion is still fake-test-only and public activation remains disabled.

Later model-free probes found a workable OS topology: a temporary helper
with host PID/cgroup namespaces could observe Docker's source PID; a unique
custom cgroup parent survived source stop and the same retained FD changed
from `populated 1` to `populated 0`. A `setsid` descendant stopped writing
while an independent outside job kept advancing. The source, helper and
empty custom parent were removed. The first simple container leaf cgroup was
deleted by Docker on stop, so it cannot supply a post-stop `cgroup.events`
read. A sidecar smoke instantiated the actual retained-parent class on a
custom parent. The bounded result and limits are in `verification.md`.
These experiments do not supply an authenticated durable broker, T053 job
admission, all-path restart denial or a production source-exclusion result;
T054–T057 remain unchecked and no account seat moved.

The user requested implementation of the
[Claude CLI supervised-jobs decision](../../openspec/changes/separate-swap-ctx-handoff/claude-cli-supervised-jobs-decision.md)
under the separate [capability contract](contracts/claude-cli-supervised-jobs.md).
T052–T057 in `tasks.md` govern the new work. Preserve the historical v1
PGID contract and fourteen INCONCLUSIVE Bite 4 results below. The scratch
seat-move probe is narrow recovery evidence, not an OS containment or
single-owner proof. Keep public activation unsupported until integrated
source exclusion, restart denial, exact CLI resume and fault tests pass;
another real-account canary needs its own authorization.
The selected source provider is a dedicated Linux Docker container with the
supervisor and admitted jobs outside it; its design is in the new contract.
T052 documentation and T053 private durable-state ledger are complete. The
canonical focused T053 gate passed seven tests, with 2,595 deselected. An
internal T054 Docker candidate now has a private mutation journal, bounded
admission checks and offline fake-engine/cgroup tests. The combined focused
`tests/run.sh -k 'test_lane_managed_docker_source or test_lane_managed_supervised_jobs'`
gate passed 13 tests. Positive exclusion remains fake-test-only: a trusted
host broker has not established Engine-host identity, retained-FD-to-host
cgroup-path custody or admitted-job process membership. There is no public
route, live Docker run or CLI invocation in this slice. T054–T057 remain open.
Do not interpret `target-observed` ledger state as completed
native-child continuation or production release.

The September 26 Claude Code wrap-up allowance may let A finish a five-hour
limit turn before swap control entry. It is a cooperative first path, not an
exclusion witness or a promise that every native child/tool finishes. Keep A
as controller until it stops; then durably fence, verify the Docker domain and
reconcile histories, files and jobs before B resumes. The forced-stop path is
still required when wrap-up is absent or incomplete. The internal T054 slice
is the last verified code checkpoint; it does not supply a production OS
exclusion witness.

## Latest checkpoint — fourteenth Bite 4 INCONCLUSIVE; T050 offline correction approved

The one user-authorized fourteenth run used commit `a260975` and preflight seal
SHA-256 `3341446309398552f83ae0094145584f6ceee1c14064e34f08d67a5b6860c835`.
It exited 2 with positive reason `target-history-query-result-incomplete`.
Source stop/removal, copy, history custody, durable release, target launch,
target stop/removal, and final custody occurred. The exact-parent human-origin
query result and one assistant frame were observed. The gateway saw exactly
one valid parent `/v1/messages` request/response, no nested tool, and a
successful response write.

The CLI reader also parsed one extra JSON mapping during the active window.
Its type was neither assistant nor result, and exact type, subtype, and order
were not retained; it may have arrived during bounded shutdown drain.
`unexpected_frame_count=1`, `read_complete=false`, `unparsed=0`, and
`read_failed=false`. The query is incomplete; this is not a runtime contract
violation finding and establishes no PASS or known FAIL. The negative arm was
not run solely because of `positive-cleanup-incomplete`.

Astra's sealed review matched all 48 file hashes and sizes. Source removal
sequence 36 preceded release 120, target intent 121, and target creation 123;
target removal was sequence 153. Source and target exits were 137 and
harness-enforced. The exact 52,825-byte source-parent prefix and saved edit
were retained. Target transcript size was 58,164 bytes with one other
configuration mutation, so whole-tree immutability is not established. Current
inventory is zero labeled containers and four unattached old/new
source-state/target-state volumes. The one-run authorization is consumed; no
further run, cleanup, retry, or deployment is authorized. Bite 5 remains
pending and production unsupported.

Seal manifest SHA-256:
`4623db6214ed86a01a1887dfd424400458ab950eff9fc16b9fb9905f6962f7de`.
Report `8658716287e2bcf8c28b12d422d06c4ed54ad5cdcd096ddcb4dd8945c7893309`;
stdout `636a1622fd9302f038d897f09eafebf0d788f65d00c1a52cc854c0a099cb341d`;
source envelope `05c34a747add6748b4b3a77c26f2ef72581270edf9d8a3f4ef5e91db8df037e7`;
arm ledger `a0b1443107fd35aee12faea673ccab49e89a29984cb94a70e18d998185a9b804`;
inventory `af391f032af5d6d9c41e40572689ff11b4f9fc3627d6a00e483494ee845ea507`.

Any future diagnostic needs a bounded ordered projection of every target-query
frame header, including type/subtype, schema, origin, session correlation, and
query-read versus shutdown-drain stage. Persist the exact target report
privately before teardown, following T050's source-report pattern. Do not
retain bodies, paths, or content; keep unknown discriminators private and the
extra-frame refusal unchanged until a type is identified against the pinned
schema. `rate_limit_event` and `turn_duration` are plausible SDK metadata
examples only, not observations.

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

## Next-session action — read-only fourteenth-run evidence assessment

Start in this existing worktree and branch. Read this checkpoint together with
[`contracts/source-only-diagnostic.md`](contracts/source-only-diagnostic.md),
[`runbook.md`](runbook.md), [`live-validation.md`](live-validation.md), and
[`verification.md`](verification.md). The fourteenth one-run authorization
is consumed. Its result is INCONCLUSIVE because the target query reader saw an
additional parsed mapping frame of unknown type/order; do not treat this as a
known runtime violation or relax the extra-frame refusal. Four unattached
old/new source/target volumes remain preserved. No further runtime, cleanup,
retry, or deployment is authorized.

Review the bounded frame-header evidence need described above and T051 in
`tasks.md`: exact target report persistence before teardown, ordered
header-only facts with query-read versus shutdown-drain stage, and offline
privacy/boundary tests, subject to Astra architecture review. Keep the current
gate unchanged until any discriminator is identified against the pinned
schema. Bite 3's OS witness/all-path restart fence remains absent, so Bite 5
cannot PASS. Preserve the sealed evidence and all inherited/current files.

Do not infer Bite 4 completion, production containment, or a Bite 5 verdict
from T050's offline gate or the fourteenth or earlier INCONCLUSIVE runs. Any
proposed protocol or gate change requires a separate review and authorization.
These result documents should be committed and pushed under the existing user
authorization; this documentation turn did not perform the landing. Do not
deploy or activate public v1 lifecycle behavior.

Maintain the named roles: Astra is architecture lead, Sol High is runtime and
offline-gate executor, and Luna Max is implementation writer. Preserve all
remaining uncommitted and untracked files through the authorized landing step.
Do not deploy, activate public v1 lifecycle behavior, or mark Bite 5 passed,
failed, or inconclusive without the required evidence and an explicit decision
record.

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
