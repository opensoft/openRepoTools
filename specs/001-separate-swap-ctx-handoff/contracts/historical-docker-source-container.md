# Historical dedicated Docker source-container candidate

**Superseded September 26:** the user requires many Claude CLI sessions to
share a container that stays running. This is retained design history for the
dormant private `docker-source-container-v1` candidate, not the current
`claude-cli-supervised-jobs-v1` contract, an implementation dependency or an
instruction to stop any running container. Its original normative wording below
applies only to that superseded candidate. Code and evidence are preserved;
no deployed capability was established. See the
[current shared-session contract](claude-cli-supervised-jobs.md) and
[governing decision](../../../openspec/changes/separate-swap-ctx-handoff/claude-cli-supervised-jobs-decision.md).

## Selected provider: dedicated Docker source container

The operator selected a dedicated Docker container for production source
containment. The prospective provider discriminator is
`docker-source-container-v1`. The L1 supervisor and persistent jobs are
outside that container. A replacement Claude runtime also receives its own
container, created only after explicit release. This selection authorizes
provider implementation; it does not certify Docker configuration, CLI
compatibility, a deployed provider or an experiment.

The initial candidate platform is a local Linux Docker Engine whose host
process/cgroup namespace the supervisor can inspect authoritatively. Docker
Desktop, a remote daemon, rootless variants and other namespace arrangements
are unsupported until their actual engine/runtime/OS tuple has a separate
validated witness mapping. A client-side PID from another namespace cannot
establish container liveness or exclusion.

### Create and bind before source launch

The supervisor's Docker broker is the only managed creator, starter, exec
dispatcher, updater and remover for a lane container. Its access checks use
the durable owner and operation generation, not a container name or label.
The source receives neither Docker control access nor supervisor ownership
credentials. User-owned persistent jobs likewise receive no Docker control
or runtime-launch authority.

Before creation, persist an immutable launch intent with a unique admission
ID, source generation, exact parent UUID, source invocation, provider version,
engine endpoint identity, image content digest and complete normalized
configuration digest. Use a pinned local image; do not resolve a mutable tag
or pull during a swap. Create the container without starting it, then persist
the full returned container ID and verified inspect/configuration digest
before authorizing its first start. Names and labels aid discovery only;
they are never sufficient authority to adopt, kill or remove a container.

The launch binding also records the engine identity, observable engine
incarnation, host boot identity, isolation/runtime configuration, container
creation identity, PID namespace and runtime cgroup identity. The image
includes a verified CLI executable digest. A stable engine ID or endpoint
alone does not prove that the daemon has not restarted. Where an incarnation
cannot be established, restart-sensitive observations are unknown.

A creation or start request with a lost response is not repeated. Reconcile
the same durable admission through the broker journal and engine inventory.
Multiple candidates, missing configuration evidence or an unverifiable
identity remains indeterminate. Do not adopt an already-running interactive
CLI into this provider retrospectively.

### Configuration admission and continued validation

Validate the Engine's resolved inspect data before start, after launch,
before stop and at readiness/release. Never trust only requested CLI flags.
The allowlisted baseline requires:

- `RestartPolicy.Name` is `no`, automatic removal is disabled, and there is
  no Compose, Swarm, systemd, scheduler or other external container restarter.
- Private process and mount isolation; no host/shared PID, IPC, cgroup or
  network namespace, no privileged mode, no host devices or device requests,
  no added capabilities, and all available capabilities dropped.
- A non-root container user mapped to the intended file-access identity,
  `no-new-privileges`, reviewed active seccomp/LSM restrictions, a read-only
  root filesystem and bounded writable scratch mounts. Unconfined profiles
  and writable host cgroup/proc/sys interfaces refuse.
- Finite memory and PID limits, a reviewed runtime/entrypoint and no
  unaccounted Docker exec process, health-check command, init helper or
  alternate entrypoint. Approved helpers remain inside the same source
  domain and are included in exclusion.
- Only explicitly admitted mounts and network attachments. Unexpected
  configuration changes, new execs, network changes or identity mismatches
  invalidate the capability before further controlled dispatch.

Unsupported host enforcement or unavailable inspect fields refuse. A
successful config comparison is a prerequisite, not proof of live exclusion.
The provider must demonstrate that child `setsid`, reparenting and forked
tools remain inside this container's actual runtime domain. It cannot assume
that the old PGID remains complete.

### Mount and network limits

Mount only registered worktrees and required repository metadata, the
verified parent/child history store, the selected profile's minimal required
authentication/configuration material and the bounded job-broker endpoint.
Use stable container paths from the launch manifest and runtime-resolved host
references. Reject overlapping or aliased mounts that expose a broader host
tree. Inspect source/destination identity, read/write mode and private mount
propagation; an absent or ambiguous mount is not accepted from its request.

The Docker socket, engine TCP credentials, supervisor state store, broad user
home, unrelated profiles and privileged host-control sockets are forbidden
mounts. The job-broker endpoint authenticates a scoped source-generation
token; it exposes admitted job operations only, never arbitrary host process
adoption, container execution or controller-state mutation.

Source history may be writable while A runs. Only the source runtime and
approved history machinery may write that session before exclusion; B gains
write access after release and source exclusion. Persistent jobs must not
write Claude session history. No token/credential is copied into the durable
controller ledger. Killing the container may leave an incomplete transcript
record: preserve the bytes, use only valid runtime-supported history, and
refuse where exact history cannot be established.

Network connectivity is necessary for an authenticated Claude runtime but
does not grant host-control access. Bind an explicit reviewed network/egress
policy allowing the required model/auth services and admitted effect
endpoints. Deny Docker control, host administration and arbitrary remote
execution endpoints; do not expose unauthenticated container ports. Network
attachments, DNS/proxy settings and any policy enforcement service belong to
the compatibility tuple. Configuration alone does not prove egress policy
enforcement. A model request or remote effect already accepted before
exclusion may outlive the source; it remains separately accounted for.
Container death proves neither remote cancellation nor external completion.

### Stop and exclusion witness

Before stop, persist the source-generation deny fence and bounded stop intent
under the same serialization used for create/start/exec. Reject new source
broker requests, starts, execs, unpauses, updates and replacements. Any earlier
Docker mutation still in flight must be accounted for before the stop is
dispatched; a queued start cannot be allowed to complete after exclusion.

If the exact source container is still running after the durable fence, the
initial provider uses one explicit bounded Engine kill request with `SIGKILL`,
followed by observation. If it stopped naturally, no kill request is needed;
the same fresh exclusion witness is still required. Request acceptance is not
completion. A timeout or lost reply never causes an automatic second stop,
removal or replacement launch. Keep the stopped source object and its
history/evidence until separately authorized disposal; automatic removal
would destroy useful restart/identity evidence.

Capture a bounded, durable stream of engine events from before admitted
source start and correlate create/start/exec/update/kill/die/restart events
with the full container ID and broker journal. Docker events have bounded
replay and no controller-owned completeness guarantee; their timestamps and
silence are not an authoritative sequence or proof of no restart. The
supervisor assigns its own persisted observation sequence and records gaps.
Events corroborate fresh inspect and OS evidence; they never replace them.
[Docker documents bounded event replay](https://docs.docker.com/reference/cli/docker/system/events/).

A positive exclusion witness requires all of the following at readiness and
again immediately before release:

- The exact container identity, engine incarnation, launch/configuration
  binding and source fence still match the durable operation.
- Fresh inspect reports a terminal stopped state: not running, restarting,
  paused or under removal, with a completed exit observation and no live
  container init PID. A Docker API error or missing object is not that state.
- Authoritative host runtime/cgroup evidence establishes that the bound
  container domain has no remaining members or exec tasks, including detached
  descendants. A removed cgroup is accepted only with correlated terminal
  lifecycle evidence and intact identity custody, never as a lone missing
  path. The provider version specifies and tests the exact witness mapping.
- The broker has no outstanding source mutation and every managed restart
  path still denies the retired source generation. No later source start,
  exec or replacement admission is unaccounted for.
- The supervisor and persistent job domain remain outside the stopped
  container; live jobs retain the same admitted identity and reservations.
  History and external-effect reconciliation satisfy the surrounding
  contract independently of container exit.

Neither `docker kill` success, a `die` event, `State.Running=false`, an empty
process listing nor engine reachability alone is sufficient. The provider
must reconcile an event gap against its authoritative broker journal,
unchanged isolation guarantees and fresh OS/engine observations; if it cannot
establish complete custody, the witness remains unknown.

### Daemon loss, restart denial and recovery

An unreachable or restarted Docker daemon is not evidence that A stopped.
Container processes may survive daemon loss, so source execution and effects
remain uncertain. Retain the durable fence, job reservations and pending
intents; create no target. On reconnect, re-establish engine/host identity,
inspect the exact container, reconcile in-flight broker operations and obtain
a new complete witness. If custody cannot be restored, remain indeterminate.
[Docker's live-restore behavior](https://docs.docker.com/engine/daemon/live-restore/)
must be included in the tested daemon configuration.

Every broker restart, fresh adapter and supervisor takeover reads and checks
the durable fence before any Engine mutation. Restart policy `no` prevents
neither manual starts nor external creation, so all managed paths must route
through this broker. Unexpected external daemon control invalidates custody.
This design retains the surrounding cooperative-workload threat boundary;
it does not claim to defeat a Docker administrator deliberately bypassing
the broker. A routine workflow requiring such a bypass is unsupported.

Persistent jobs do not require A's container or a callback from A to retain
their process, output or result. They continue during daemon loss when their
own execution host remains healthy. A host/supervisor/job failure is handled
as job uncertainty, never as permission to replay. No containment operation
targets the user session, a broad host process group or the job domain.

### Provider-specific acceptance

#### Initial candidate: retained cgroup v2 parent

The initial Linux witness candidate uses a unique retained cgroup v2 parent
for each source runtime incarnation. Docker places its container cgroup
beneath that parent. The supervisor and persistent jobs reside outside the
parent's entire subtree. This is a proposed mapping, not verified support;
all Docker configuration gates above remain mandatory.

Before source start, a narrowly authorized host broker provisions an empty
parent using the selected cgroup driver's supported management mechanism.
For the systemd driver, use an explicitly managed retained slice with
validated lifecycle rules; do not manually mutate systemd-owned directories
or assume cgroupfs naming. Pin the Engine, runtime, kernel, cgroup driver and
parent-management configuration. Record the unique domain allocation ID,
host boot identity, host mount/PID/cgroup namespace identities, cgroup2 mount
identity and parent directory identity. Retain a no-follow directory handle
while observing. A path or inode number alone is not durable custody across
removal, recreation, reboot or mount replacement; never reuse an allocation.

Verify `cgroup.type` is the supported domain type and the parent's
`cgroup.events` initially reports `populated 0`. Persist the parent binding
and Docker `CgroupParent` configuration before container start. The parent
must remain allocated through stop, readiness and release. Refuse if its
manager can remove it automatically or another workload can enter it.

Docker creation may precede creation of the container's own cgroup, so a
Created container is not evidence of live cgroup placement. The pinned image
first runs a trusted entrypoint that waits without starting Claude or tools.
After start, the broker joins fresh inspect's exact container ID and init PID
to that PID's host process-start identity and unified cgroup membership. It
verifies the actual container cgroup is a descendant of the retained parent
and binds its directory identity. Re-read process and container identity
around this join to reject PID reuse or an exiting/restarting container.
Only after persisting that binding does the broker permit the waiting
entrypoint to start Claude. The entrypoint, approved helpers and any admitted
Engine exec tasks are part of the same containment domain. A failed placement
check never allows model execution and retains the uncertain source state
for explicit recovery.

For stop, the previously specified identity-bound Engine kill remains the
action; there is no implicit direct-cgroup-kill fallback. After its terminal
inspect observation, read `cgroup.events` through the verified parent
identity. `populated 0` covers the parent's entire subtree, including
descendants that changed process group or became reparented. The kernel
documents both this recursive populated state and inherited cgroup placement
on fork; process migration permissions remain a separate containment
requirement. [Linux cgroup v2 documentation](https://docs.kernel.org/admin-guide/cgroup-v2.html).

Docker may remove its now-empty container leaf. That removal is acceptable
only when the retained original parent still exists, reports `populated 0`,
and the exact stopped-container, restart-fence and mutation-journal checks
pass. This supplies positive evidence through the parent instead of treating
a missing leaf as proof. If the parent disappears or its identity changes,
the initial provider refuses a positive witness, even when Docker reports
the container stopped. Automatic reconstruction of an identically named
empty parent cannot repair that loss of custody.

The positive witness binds the verified parent identity, actual container
placement, fresh recursive populated value, exact terminal container state,
engine incarnation, source fence and broker mutation watermark. Repeat the
identity and empty-state check immediately before release under the broker's
launch/mutation serialization. A populated parent, unreadable field,
unexpected task, stale namespace, concurrent authorized mutation or lost
identity leaves exclusion unknown. Polling/inotify may wake the observer;
the fresh kernel read supplies the value. Docker events are only additional
corroboration. [Docker documents cgroup-driver-specific placement](https://docs.docker.com/engine/containers/runmetrics/).

The observer needs authoritative access to the Engine host's process
identities, unified cgroup mount and parent event files. Provisioning needs
an existing appropriately delegated cgroup subtree or a narrowly privileged
host service; ordinary membership in the Docker group does not supply this
delegation. Do not change host delegation, daemon drivers or permissions
silently. If a supervisor under the local user lacks the necessary access,
or is in a namespace that cannot establish host identity, report unsupported
before disrupting A. A future host witness helper requires its own reviewed
authentication and custody binding.

The source must have no host interface or permission permitting migration
outside the parent, and no routine external process manager may move its
tasks. A private cgroup namespace alone is not permission proof. Validate
the effective mount, privilege and broker policy and test attempted escape.
The retained-parent witness proves absence of live source processes; it does
not prove completion of buffered filesystem I/O or remote work already
accepted elsewhere. Preserve history and reconcile those effects separately.

In addition to the general gates below, verification must demonstrate a
setsid/reparented source writer and an Engine exec task excluded by the
source stop while an external admitted job remains alive. Test wrong/reused
names, mismatched full IDs, unsafe mount/config changes, stale engine
incarnations, dropped events, daemon loss with live containers, delayed
create/start replies, attempted retired-generation restart and source
history preservation. Faults must retain uncertainty and prevent B startup.
Record the exact Engine/runtime/kernel/configuration tuple; no source
container run or production capability is claimed by this document.
