# Linux shared-container session provider

Provider: `linux-session-subreaper-v1`, within
[claude-cli-supervised-jobs-v1](claude-cli-supervised-jobs.md).
Authority: [current decision](../../../openspec/changes/separate-swap-ctx-handoff/claude-cli-supervised-jobs-decision.md).
Astra owns architecture; Sol implements the latest deployment instruction.

## Boundary and kernel basis

One persistent supervisor launches a dedicated wrapper for A, independently
of the job runner and unrelated session C. The wrapper launches only A's
runtime tree. It remains a live custodian through prepare and release; B gets
a new wrapper. The shared container, C and existing jobs stay running.

Before spawning A, the wrapper sets `PR_SET_CHILD_SUBREAPER=1` and verifies it
with `PR_GET_CHILD_SUBREAPER`. Linux reparents orphaned descendants to a living
ancestor subreaper; double-fork and `setsid` do not change that ancestry.
The setting is not inherited by forked children. [Linux subreaper interface](https://man7.org/linux/man-pages/man2/PR_SET_CHILD_SUBREAPER.2const.html).

The closure argument is an inference under the custody rules below: any live
descendant has either a live ancestor that is the wrapper's child or is itself
adopted by the wrapper. The kernel reparents children before exposing the
exiting parent as a zombie, under its task-list lock; final-parent reaping does
not open a gap before reparenting. [Linux exit implementation](https://github.com/torvalds/linux/blob/master/kernel/exit.c).

One wait owner uses `waitpid(-1, WNOHANG | __WALL)` (`__WALL=0x40000000` on
Linux), consumes terminal statuses and separately records A's exact main
process status. Return zero means children still exist; only `ECHILD` ends
the drain after source launch and main terminal status are established.
`__WALL` includes clone children whose exit signal is not `SIGCHLD`; ordinary
`waitpid` alone can omit them. `SIGCHLD` stays default, with no
`SA_NOCLDWAIT`, competing thread/library waiter or `Popen.poll()` reaper.
[Linux wait semantics](https://man7.org/linux/man-pages/man2/waitpid.2.html).

Nested child subreapers remain beneath a live ancestor in A's subtree and do
not by themselves defeat closure. The initial supported configuration stays
in one PID namespace; namespace mutation, external ptracing and launching work
through an outside service other than the admitted job supervisor are outside
the supported source path. Pin and verify effective CLI tools, hooks, plugins
and helpers accordingly. A host process scan cannot substitute for custody.
[Linux namespace reparenting](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html).

## Admission and custody protocol

1. Under the durable managed ownership lock, claim lane/generation and exact
   parent UUID before spawning A. Also exclude duplicate history ownership
   across lanes using a shared runtime registry keyed by history-store identity
   and parent UUID in this host/PID namespace. Persist the immutable manifest,
   source incarnation, provider/domain nonce and launch intent before spawn.
2. Start the single-purpose wrapper independently of A's terminal lifetime.
   Bind its PID/start token, boot and PID-namespace identity, random incarnation,
   authenticated control endpoint and journal identity. Set/verify subreaper
   before source fork. A's child waits on an admission pipe before exec; bind
   its PID/start identity and flush the journal before allowing it to execute.
   Lost gate/custody refuses exec. Do not infer successful launch from intent.
3. Only this wrapper reaps this source tree. Close supervisor-control secrets,
   journal descriptors and unrelated inherited FDs before child exec. Immutable
   per-runtime MCP/settings/profile references and generation-scoped job
   credentials cannot overwrite another runtime's config or grant ownership
   transfer. Do not use a broad environment or profile switch.
4. A does optional foreground wrap-up before control entry, then exits normally.
   Record actual main terminal status independently of turn/task completion.
   After control entry a bounded graceful exit action may run only under its
   validated CLI control route; no extra model turn is requested. On timeout,
   refused exit or remaining descendants, retain claims and B stays absent.
5. Reap all child types to `ECHILD`. Permanently seal this wrapper against
   further spawn, including helper subprocesses. Persist the source exit status,
   final drain observation, fence and monotonic journal sequence durably. A
   nonzero/signal exit is recorded honestly and cannot bypass history/effect
   reconciliation or become a successful task-completion claim.
6. Before readiness and again at release, obtain a fresh authenticated challenge
   from the same live wrapper, verify its identity/subreaper state/sealed spawn
   policy and repeat the empty-child observation. Reconcile all pending launch
   intents under the same ownership/fence serialization. The challenge and
   journal digest bind source, domain, parent, generation and observation.
7. Reconcile history, effects, live job records and resource reservations.
   Explicit release consumes one target intent before B is spawned under a
   NEW wrapper. Stale A commands, reused release or a duplicate source/target
   owner refuse. Never make the source wrapper also the target launcher.
   Return that wrapper's exact attach locator while B waits at a fresh trust
   dialog. A separate observation retries custody of the same launch and
   opens B model input only after exact SessionStart, claim adoption, control
   binding and a final current-owner check. It never repeats the spawn.

Use the existing T053 source-witness schema unchanged: its complete-membership
and escape-coverage fields become true only after the above checks, its active
source process count is zero, and `source_domain_id` binds the wrapper nonce.
The digest covers the richer private custody journal and fresh challenge.
Observation watermarks must advance across source/history/job observations;
caller-provided booleans are not a provider witness.

## Workspace edits and profile eligibility

The initial native roster is Read/Glob/Grep/Agent/SendMessage, with
same-parent native-child replies awaited in the foreground and external
session routing disabled. Native Edit/Write and
Bash/PowerShell are omitted and explicitly denied. All workspace mutation,
including ordinary coding edits, is available through admitted supervisor MCP
jobs; run/status/output/wait must make those edits usable and observable.
Admission atomically reserves the registered worktree before dispatch, so a
second writer cannot race a live or uncertain job. Validate an actual edit and
conflicting-write refusal in the installed route. Optional edit/write MCP
convenience tools must use that same admission/result boundary. This is a
cooperative workload policy, not a filesystem sandbox for hostile commands.

A native file-tool PreToolUse hook is not the initial enforcement mechanism:
command-hook errors, unavailable handlers and timeouts can continue through
normal permissions. Any later native-write route needs default-deny runtime
permission behavior plus durable tool-use reservation across execution and
fault-tested hook behavior. [Claude hook failure semantics](https://code.claude.com/docs/en/hooks#timeouts).

Keep the existing profile resolver's inactive-profile gate unchanged. The
operator explicitly selected source `team05d` and target `team05j`. If their
existing, identity-matched host-local provisioning catalog still says planned
and its directory is read-only, a private immutable deployment manifest may
project exactly those two planned entries to active. Record the original
catalog digest, unchanged canonical identity/path/auth/family, observed planned
status and the operator's explicit selection. Pass the projection only through
the managed launch's supported `CLAUDE_PROFILES_MANIFEST` setting; never mutate
global environment or profiles/credentials. Disabled/retired entries cannot be
promoted. Active here means admitted existing configuration, not current paid
seat availability. Target launch still follows verified A exit, operator seat
movement, explicit release and actual target account identity checks.

## Jobs, recovery and limits

The job supervisor is not A's child. A's stdio MCP bridge can be a source
child, but only forwards authenticated admission/control to the independent
supervisor; its own exit is included in A's drain. Jobs are admitted before
spawn, with separate custody, IDs, output and reservations. A cannot acquire
an arbitrary already-running process as a job. The same wrapper mechanism may
be reused for a job's subtree, with a distinct lifetime and journal; never
share A's wrapper or its stop boundary.

If only the controller restarts, it may reconnect to the exact original live
wrapper and journal and continue observation under the persisted generation.
It cannot repeat a possibly dispatched launch. If the wrapper dies, its
children can be reparented outside its custody. Preserve indeterminate state
and deny B even if a replacement wrapper or a PID scan reports empty. Initial
recovery does not reconstruct lost custody, kill processes globally or restart
the container. Wrapper replacement requires a separately proven recovery path.

The protection model is cooperative managed processes under one local user,
not hostile same-UID code or an administrator. A native tool or job requesting
an external runtime launcher is not made safe by subreaper status. Reject that
source configuration or account for the effect through its separate admitted
service. Local process closure says nothing about already accepted remote
requests, durable history integrity or logical model-task completion.

## Required implementation evidence

Use the canonical test wrapper for code tests. Exercise real unprivileged
Linux process fixtures: ordinary child, `setsid` double-fork writer, nested
subreaper, child still live after A exits, and clone children without SIGCHLD
(or refuse that unsupported platform/test capability). No live child permits
positive closure. Test source exit/journal crash points, absent main status,
`WNOHANG=0`, wrapper loss, duplicate history-owner claims and stale challenge.
A fresh adapter/controller must reconnect to original custody or refuse.

Then use independent Claude A and C in the SAME container through the pinned
launcher: A's foreground child/history and graceful exit, an admitted job that
keeps identity and advances output, C/container/config/auth unchanged, no B
before reconciliation/release, and one B exact-parent continuation afterward.
Fault arms cover stale A requests/restarts, duplicate B, lost ACK and unknown
history/effects. Keep real CLI behavior distinct from process-only fixtures.
Runtime validation and installation follow the user's deployment instruction;
record concrete named canary profiles/lane before any user-operated seat move.
