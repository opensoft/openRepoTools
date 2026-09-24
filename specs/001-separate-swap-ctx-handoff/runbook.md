# Five-bite runbook: source containment and exact-parent resume

**Latest state (2026-09-24): bites 1–3 are complete; none of fourteen full
Bite 4 runs produced a PASS. The fourteenth run used commit `a260975` and
preflight seal SHA-256
`3341446309398552f83ae0094145584f6ceee1c14064e34f08d67a5b6860c835`. It
exited 2, INCONCLUSIVE with positive reason
`target-history-query-result-incomplete`. Source stop/removal, copy, history
custody, durable release, target launch/stop/removal, and final custody
occurred. The exact-parent human-origin query result and one assistant frame
were observed; the gateway saw one valid parent `/v1/messages` request and
response, no nested tool, and a successful response write. One additional
successfully parsed JSON mapping of unknown type/subtype/order made
`unexpected_frame_count=1` and `read_complete=false`; it may have appeared
during bounded shutdown drain. Unparsed frames were zero and the reader did
not fail. The query remains INCOMPLETE; no PASS or known FAIL was established.
The negative arm did not run solely because of
`positive-cleanup-incomplete`. The current inventory is zero labeled
containers and four unattached volumes (old and new source-state and
target-state). The one-run authorization is consumed; no further run, cleanup,
retry, or deployment is authorized. Bite 5 remains pending and production
unsupported. T050's future-only source-report correction passed Astra
architecture review and Sol's canonical focused gate: 427 passed, 2,168
deselected, zero failures.** This is the operator sequence and record for the
bounded diagnostic. The source-only containment domain (the source phase of
the two-domain experiment) and separate post-release target design are in
[source-only-diagnostic.md](contracts/source-only-diagnostic.md). Bite 4 uses
two separate runtime domains: source first, then target after verified source
stop, history custody, and durable explicit release. Sol High is the sole
test and runtime executor. No live account, credentials, external network,
installation, deployment, cleanup, or production activation is authorized.

T049's separate diagnostic-only query mode is architecture APPROVED; its
expanded canonical scoped gate passed (420 passed, 2,168 deselected, zero
failed). The later separately authorized thirteenth run did not reach copy,
release, or the diagnostic query: source-report schema validation failed after
source stop/removal and target-state volume creation. Its source exception was
not retained. The unbound legacy/source `parent_uuid` reference is a
deterministic static cause candidate, not a proven historical exception.

T050 is the approved future-only offline correction: remove that unbound
initializer, add bounded allowlisted error-site metadata, persist and validate
the exact source report privately before further effects, quarantine malformed
fallbacks with a fixed public reason, retain FAIL for an otherwise-valid
explicit target-code reach, and keep unknown reach INCONCLUSIVE. Sol's focused
canonical gate passed 427 tests, 2,168 deselected, zero failures. This does not
change the thirteenth result or authorize another runtime. Full-suite failure
triage and gate digests are in `verification.md`.

The full repository suite ran once with 2,560 passed, 28 failed, zero skipped,
five warnings, in 3,951.61 seconds, before the ten stale loopback fixtures
were fixed. The expanded T049 scope now passes. Fourteen native
context/restoration failures hit the unchanged unsupported controller gate.
An isolated three-node rerun passed the CLI unsafe-parent and daemon-route
cases but failed the CLI persistent-lifecycle case on an ownership conflict;
the shell aggregate was not rerun. The full suite was not rerun after those
fixture fixes, so this is not a full-suite pass or a runtime-conclusive result.

T049 defines an offline-only, separate diagnostic query mode in
[`source-only-diagnostic.md`](contracts/source-only-diagnostic.md). The
existing `strict-v1` profile remains the default, and its sticky gate remains
unchanged. The two-domain terminal-task diagnostic mode requires explicit
profile/fingerprint and durable-intent binding. Any runtime attempt requires
separate explicit authorization; this documentation does not authorize one.

The T046 future-only target handoff requires a complete, digest-only source
terminal-task seed linked to the source parent and invocation. The seed is
bound into the source-phase digest, durable release and target-launch intents,
and target-spec fingerprint. The ninth and tenth runs exercised unavailable-
seed refusals before release; the eleventh and twelfth bridged the source seed
and established release candidates, but remained INCONCLUSIVE under the unchanged
startup-task gate. T047 repaired the v2 diagnostic path. T048 adds the v3 seed
envelope, bounded digest-only rejected-hook diagnostics, and a strictly
validated SDK-sidecar identity bridge. These changes do not amend historical
reports, establish Bite 3 containment, or enable production support. T049's
separate diagnostic-only mode does not alter the default `strict-v1` sticky
gate; it may proceed only when its independently bound prerequisites in the
linked contract pass.

## Historical T047 source-native terminal seed repair — architecture/offline PASS; tenth runtime INCONCLUSIVE

The future-only T047 implementation preserves the terminal source observation
instead of synthesizing a source-target match. The v2 envelope separately
binds one earlier `task_started` record, terminal `task_notification`, and
agent proof. Source hooks are enabled for bounded observation; an unresolved
early hook joins only on exact session/tool-use digests, with any observed
task ID also exact. Direct or hook-derived agent identity must map uniquely to
the started task, and source-side correlation stays all unknown until target
events exist. Optional target agent/tool/task-type fields are not invented;
present conflicts fail correlation. `task_updated.patch.status` is recorded
but an update-only terminal does not seed this bounded tranche. The sticky
startup gate is unchanged. Bounded source projection diagnostics are included
in the source-phase digest and expose no raw IDs or paths.

Astra's final architecture review and Sol's formal offline gate passed. Sol
ran `tests/run.sh --parallel-safe -k 'two_domain or native_task or native_hook or hook_ack or source_terminal_seed'`:
210 selected and passed, 2,270 deselected, zero failures/errors/skips, in
13.02s. Frozen source hashes, private artifact digests, and Luna's 207-test
development smoke are in `verification.md`. The tenth runtime attempt used
this frozen repair but was INCONCLUSIVE before release/target creation:
`source-native-task-terminal-seed-unavailable`, detailed reason
`terminal-task-hook-evidence-incomplete`. See the tenth-run record below and
`verification.md`. At the T047 checkpoint, the tenth authorization was
consumed and no eleventh attempt had yet been authorized; that wording is
historical. T048 and the later eleventh result and consumed authorization are
recorded above.

## Historical checkpoint — T048 SDK-sidecar identity bridge; eleventh runtime INCONCLUSIVE

T048 retains a structurally valid callback/task-tool mismatch as unresolved,
task-ID-free hook evidence after full shape validation, with a success ACK and
an unchanged observed callback tool digest. Bounded diagnostics distinguish
callback, hook-input, and current task/session/tool identity digests, including
rejected callback/input conflicts. At source finalization, a distinct strict
SDK-sidecar proof may bridge the hook agent to the task-start tool only after
unique parent-sidecar tool linkage, top-level parent/child identity checks,
and exact `SubagentStop` transcript-path proof. Bounded no-follow scans and
detached validation fail closed on missing, ambiguous, conflicting, malformed,
unsafe, or overflow evidence. This does not change the historical tenth
result, authorize cleanup, or decide Bite 5.

Astra architecture review passed. Sol's formal selector passed 243 tests, with
2,270 deselected and zero failures/errors/skips; code hashes and complete
formal artifact digests are recorded in `verification.md`. The separately
authorized eleventh Bite 4 attempt ran once: the source v3 SDK-sidecar seed was
available, release candidate was true, and release/launch/target creation
occurred, but the target's complete stopped task notification kept the sticky
gate closed. The attempt exited 2, INCONCLUSIVE with
`startup-task-event-observed`; history query was skipped, negative arm did not
run, and no loaded-history proof exists. Seventeen volumes (11 source-state,
six target-state), five older stopped containers, zero running, and zero
current target containers remain preserved. The one-run authorization is
consumed. Next action is read-only protocol investigation; no Docker retry,
cleanup, or twelfth attempt is authorized. Bite 5 remains undecided.

## Twelfth full Bite 4 runtime — INCONCLUSIVE; authorization consumed

The twelfth invocation exited 2 with sanitized status INCONCLUSIVE. The source
v3 terminal seed was available, the release candidate was ready, and exact
copy/pre-release custody passed. `observer_complete=true` and
`cleanup_complete=false`. Source stop/removal and target stop/removal were
harness/engine enforced with exit 137. One complete stopped target
`system/task_notification` matched session/task; optional agent/tool identity
was unknown and its event UUID differed from the source parent. The sticky
gate recorded `successful_result_seen=true` and `history_query_allowed=false`;
no history query or read was sent. No
parent/child startup messages were observed, and the negative arm did not run.

Event sequence: source stop 34 and removal 36; copy verification 92;
pre-release custody 119; durable release 120; launch intent 121; target create
123; target stop 151 and removal 153; final helper removal 179; final custody
180. The sealed result digest is
`4289f073b7c8508633f13c829d0ed670c813f917480ff106bd0525d14ee24294`. Final
custody retained the saved edit and linked source-parent history prefix, but
the target parent JSONL grew from 52,825 to 55,372 bytes and
`other_config_mutation_count=1`; it does not establish whole target-tree
immutability. The public negative-arm reason is misleading: release candidate
readiness was true, while `cleanup_complete=false` was the unmet prerequisite
after preserving the INCONCLUSIVE run. Full artifact hashes are in
`verification.md`.

The sanitized report records `bite5_decision=pending-review`,
`production_disposition=unsupported`, and `support_claim=false`. The run gives
no loaded-history proof or Bite 3 OS witness/all-path restart fence, so it is
not a Bite 5 verdict. The run's pre-cleanup inventory was 19 volumes (12
source-state, seven target-state), four older stopped Bite 4 containers plus
one metadata diagnostic container, zero running, and no current target
container. A separate explicit authorization later covered exact removal of
that inventory; the completed postflight is recorded below.

### Post-run authorized cleanup — complete

After verifying the sealed twelfth-run evidence, Sol High completed the exact
authorized cleanup on 2026-09-24. Preflight found the 19 labeled diagnostic
volumes and five stopped containers (four Bite 4, one read-only metadata
diagnostic), with no running containers or unrelated attachments. Postflight
confirmed all 24 allowlisted resources absent. The sealed bundle and all 36
manifest entries remain unchanged. No prune, evidence deletion, or unrelated
resource removal occurred. The private mode-0600 allowlist artifact has
SHA-256
`d6ea783b66a4bee326ee23b83d80a82797f2f633db19831b131b0ac4cd0a4d78`. The
twelfth run remains INCONCLUSIVE, Bite 5 remains pending, production remains
unsupported. At that historical checkpoint no thirteenth attempt was
authorized; a later one-run authorization and its consumed INCONCLUSIVE
result are recorded below.

## Five bites and current disposition

| Bite | Purpose | Current disposition |
| --- | --- | --- |
| 1. Evidence map | Inventory SDK lifecycle fields, current hook/runner evidence, and the limits of existing probe observations. | **Complete.** The handoff's Bite 1 map records source locations and the limits of hook, process-group, and history observations. |
| 2. Opt-in hook diagnostic | Add bounded default-off native hook observation and offline correlation coverage. | **Complete.** Frozen focused snapshot: 153 passed, 2,140 deselected. Hashes and scope are in `verification.md`. This is local diagnostic evidence only. |
| 3. Containment and restart definition | Define operation-bound source domain, membership/escape coverage, durable all-path restart fencing, observation freshness, and fail-closed outcomes. | **Complete.** Astra reviewed and passed the contract. Current production producer is absent; preflight remains unsupported. |
| 4. Bounded two-domain experiment | Observe source stop and history preservation, then durable explicit release, then one exact-parent target startup in a separate container. | **Not completed.** The twelfth run remained INCONCLUSIVE at `startup-task-event-observed`; the thirteenth remained INCONCLUSIVE before copy/release/target creation with `effect-or-observer-uncertain`; the fourteenth reached target launch and final custody but remained INCONCLUSIVE with `target-history-query-result-incomplete`. Its exact-parent human-origin result and one assistant frame were observed; one additional parsed JSON mapping of unknown type/subtype/order made the read incomplete. No PASS or known FAIL was established. Zero labeled containers and four unattached old/new source/target volumes remain preserved. All fourteen run authorizations are consumed; no further run, cleanup, retry, or deployment is authorized. Bite 3 containment, whole-history restoration, and Bite 5 remain unproved. |
| 5. Evidence decision | Reconcile Bite 4 artifacts against Bite 3 and decide the next authorized step. | **Pending.** The fourteenth result is INCONCLUSIVE, not a Bite 5 verdict. Review its incomplete query evidence alongside Bite 3 requirements; the missing OS witness and all-path restart fence prevent a Bite 5 PASS. No further runtime, cleanup, or production action is authorized. |

Statements below that say no fifth, sixth, seventh, eighth, ninth, tenth,
eleventh, twelfth, or thirteenth run was authorized record earlier
checkpoints. The seventh through fourteenth attempts and the separately
authorized metadata read have run once and are recorded below; their
authorizations are consumed. The twelfth-run cleanup covered only its exact
allowlist. The thirteenth and fourteenth runs left two unattached labeled
volumes each; all four remain preserved and no cleanup is authorized. Do not
replay a command or infer a Bite 5 verdict from metadata or runtime evidence.

## Fourteenth full Bite 4 run — INCONCLUSIVE; authorization consumed

The user-authorized fourteenth run used commit `a260975` and preflight seal
SHA-256 `3341446309398552f83ae0094145584f6ceee1c14064e34f08d67a5b6860c835`.
It exited 2 with positive reason `target-history-query-result-incomplete`.
The exact-parent human-origin query result and one assistant frame were seen.
The gateway saw exactly one valid parent `/v1/messages` request/response, no
nested tool, and a successful response write.

The CLI reader also parsed one extra JSON mapping during the active diagnostic
window; its type was neither assistant nor result, and exact type/subtype/order
were not retained. It may have appeared during bounded shutdown drain.
`unexpected_frame_count=1`, `read_complete=false`, `unparsed=0`, and
`read_failed=false`. This leaves the query incomplete, without a PASS or
known FAIL finding. The negative arm did not run solely because of
`positive-cleanup-incomplete`.

The source was stopped and removed, copy and history custody completed, and
durable release, target launch/stop/removal, and final custody occurred. Astra
verified all 48 sealed file hashes and sizes. Source removal sequence 36
preceded release 120, target intent 121, and target creation 123; target
removal was sequence 153. Both source and target exits were 137 and
harness-enforced. The exact 52,825-byte source-parent prefix and saved edit
were retained. The target transcript was 58,164 bytes and had one other
configuration mutation, so this does not establish whole-tree immutability.
No runtime contract violation was found. The missing Bite 3 OS witness and
all-path restart fence mean Bite 5 cannot PASS.

Current inventory is zero labeled containers and four unattached volumes:
old and new source-state and target-state volumes. No cleanup, retry, or
deployment is authorized; the one-run authorization is consumed, and no
further runtime is authorized. Bite 5 remains pending and production remains
unsupported.

Seal manifest SHA-256:
`4623db6214ed86a01a1887dfd424400458ab950eff9fc16b9fb9905f6962f7de`.
Report `8658716287e2bcf8c28b12d422d06c4ed54ad5cdcd096ddcb4dd8945c7893309`;
stdout `636a1622fd9302f038d897f09eafebf0d788f65d00c1a52cc854c0a099cb341d`;
source envelope `05c34a747add6748b4b3a77c26f2ef72581270edf9d8a3f4ef5e91db8df037e7`;
arm ledger `a0b1443107fd35aee12faea673ccab49e89a29984cb94a70e18d998185a9b804`;
inventory `af391f032af5d6d9c41e40572689ff11b4f9fc3627d6a00e483494ee845ea507`.

The bounded next diagnostic evidence need is a private, ordered projection of
every target-query frame header: type/subtype, schema, origin, session
correlation, and whether it arrived during query read or shutdown drain. Do not
retain frame bodies, paths, or content, and do not relax refusal for any extra
frame. Plausible SDK metadata such as `rate_limit_event` or
`turn_duration` was not observed; identify any discriminator against the
pinned schema before changing interpretation.

## Historical thirteenth full Bite 4 runtime — INCONCLUSIVE; authorization consumed

The user authorized exactly one run and Sol reviewed/froze the command. It
exited 2 after about 20 seconds. The public report is overall INCONCLUSIVE,
with `bite5_decision=pending-review`, `production_disposition=unsupported`,
and `support_claim=false`. `explicit_release_selected=true` records the
selection only; release was not reached. The positive arm is INCONCLUSIVE with
`effect-or-observer-uncertain`, `observer_complete=false`,
`cleanup_complete=false`, and `release_candidate_ready=false`. The negative
arm is `not-run` with reasons `positive-release-candidate-not-established`,
`positive-cleanup-incomplete`, and `positive-observer-incomplete`; no target
container was created.

The source runtime report failed schema validation after source stop/removal
and target-state volume creation, before copy, release, or target creation.
Source stop, stop-container, and removal ledger artifacts exist; the source
was observed running after its phase and then stopped and removed. The inner
source exception was not retained. The unbound `parent_uuid` reference in the
legacy/source initializer is a deterministic static cause candidate, not a
directly proven historical exception. Quarantine counters were all zero,
`volumes_removed=false`, and leftovers require manual review. The preserved
inventory is zero labeled containers and two unattached volumes (one
source-state and one target-state). No event indices were present in the
sealed artifacts. At that thirteenth-run checkpoint, no retry, cleanup, or
fourteenth authorization was allowed.

Sealed manifest SHA-256 is
`5815a42167d5a772131368264111f9cb124f726fe33e101dee318eb3f8bd9d23`; sanitized
stdout is `cd94d74854d88431c178b17b8893179e34b8821034e4570f02986051a86f374a`,
private report is `55d8311397fa473ee85612ea0e95c60ce6aa0caee074d2f360632964b6ab146e`,
and abort ledger is `b898eabb9f181fdcbf8a0c00d11f36090417d9ad62059bc8a183072d8ba557a8`.
Runtime pins: SDK 0.2.153; CLI 2.1.273 SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`; image
SHA-256 `a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094`.
T050's future-only correction and 427-test offline gate are recorded above
and in `verification.md`; they do not rewrite this result. Bite 5 remains
pending and production remains unsupported.

## T035 future-only tmpfs/quarantine correction — offline PASS

Astra's targeted review passed, and Sol's focused selector
`tests/run.sh --parallel-safe -k two_domain` passed **59 tests, 2,293
deselected in 6.74s** inside `py-bench`. Frozen harness/helper/test hashes,
JUnit and captured-output hashes are recorded in `verification.md`. This
corrects the exact Docker Created-state tmpfs representation and quarantine
accounting only. It does not runtime-verify the correction, change any of the
three INCONCLUSIVE Bite 4 results that existed at the T035 checkpoint, itself
authorize cleanup or another attempt, or resolve Bite 5. A later separate
one-run authorization is recorded below. At that checkpoint, three
source-state volumes and the never-started Created source container were
preserved; the fourth-run checkpoint raised the inventory to four volumes and
two containers. At the fifth-run checkpoint, five volumes and three stopped
source containers were preserved. The sixth-run inventory is recorded below.

The first three harness results, distinct artifact hashes, and the event-stream
diagnosis are in [`live-validation.md`](live-validation.md). At that point,
three source-state volumes and one never-started Created source container were
preserved for manual review. Do not remove, mount, relabel, or reuse any of
them during documentation or read-only diagnosis. The original two volumes
remain untouched; the fourth run's additional preserved resources are recorded
in its separate section below.

The read-only diagnosis established that Docker's volume event did not carry
the custom run/role labels, even though current volume inspection showed those
labels. T033's future-only correction retains the label-filtered container
stream and adds an unfiltered volume-only stream with exact preregistration and
bounded independent inspection. Astra's targeted architecture review passed;
Sol's focused offline selector passed 39 tests. The correction also requires
nonempty consistent engine actor identity and waits a bounded time for expected
mount/unmount events while checking both streams. This is not runtime
verification. The user authorized a first new Bite 4 test, which was executed
and aborted INCONCLUSIVE as recorded below. Sol's preflight passed, and Astra's
read-only assessment found no concrete blocker: the original uncertainty was
event observation only, no source was stopped or launched, and the old volume
had no attached containers. The follow-up used fresh run IDs, volumes, ledger,
and artifacts; the old volume remains untouched. That assessment was limited
to the one diagnostic follow-up and grants no production or deployment
authority. After the separate smoke and offline correction, the user later
authorized one third full Bite 4 attempt. That attempt executed and is recorded
below as INCONCLUSIVE before source startup. Its one-run authorization is
consumed; at that historical point no further run or cleanup was authorized.
The user's later one-time fourth-attempt authorization is recorded separately
below and remains gated on fresh preflight.
Astra passed review of Luna's future-only mount-builder/private-stderr
correction and Sol's focused offline gate passed 41 tests. The separate
create-only smoke authorization and result are recorded below; it does not
establish Bite 4 completion. The later third full runtime also stopped before
source startup and is recorded in the following section.

## 2026-09-22 T034 isolated Docker-create smoke — narrow PASS

After the T034 offline correction passed review and tests, the user separately
authorized one isolated Docker-create smoke. Sol used the exact frozen
_container_create_command source variant (harness SHA-256
c5c183cb215ecf56f3ff028dd2e4175364a1d7f2720df6fcff29e9baadc7cdac) with the
pinned local image ID
sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d.
Docker created one fresh run-labelled container with one fresh labelled
engine-managed volume. Independent inspection confirmed Created state,
Running=false, and the writable volume mount RW=true. The container was never
started; no SDK/runtime or network activity occurred.

Sol removed only this smoke-owned container and volume, then independently
verified both were absent. The two pre-existing source-state volumes were
untouched, and zero run-labelled containers remained. This PASS establishes
only that the current builder's create specification is accepted and has the
expected writable mount. It does not confirm that the earlier exit-125 failure
was caused by its former rw token because the exact prior daemon stderr was not
retained. It is not a Bite 4 source/target experiment and does not change the Bite 4
INCONCLUSIVE results or the pending Bite 5 decision. A later, separate user
authorization for a third full source/target attempt is recorded in the next
section; the smoke itself did not grant that authority.

Private evidence SHA-256 values: commands
f6136e05ab0e834d41682e655c41c79f005d88786aaae5347f7806819badd517; inspect
5cad66170547b9a015dbbf2abd2791210f7bcb2b8718e6fe3f384deb3de7be0d; cleanup
3f15320367ab36900f00fe8e3ac19e292ab96081018b70556265077c90ba50d3. Raw
container/volume IDs and private paths remain in Sol's restricted record.

## Third full Bite 4 attempt — INCONCLUSIVE before source; authorization consumed

The user explicitly authorized one third full Bite 4 attempt after Astra's
read-only pre-run assessment and Sol's fresh read-only preflight passed. Sol ran
it with a fresh private artifact parent and new run identity; the earlier two
source-state volumes were untouched. All three full attempts are INCONCLUSIVE.
This third authorization is consumed. Do not retry, clean up, or start a fourth
full run.

The mount-builder/private-stderr correction also passed Astra's review and
Sol's offline selector tests/run.sh --parallel-safe -k two_domain: 41 passed,
2,293 deselected in 9.09s. That is offline-only evidence and does not confirm
the earlier exit-125 cause or runtime behavior. The T034 hashes below identify
the candidate frozen for this newly authorized attempt.

The frozen candidate to execute is identified by these SHA-256 values:
harness c5c183cb215ecf56f3ff028dd2e4175364a1d7f2720df6fcff29e9baadc7cdac,
helper 4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695,
and tests
3f7c5f63af5331d7bdc4116b04535bc6f549bb852b05a68cef318b115ab9e1ac.
Sol's preflight pins SDK 0.2.153, CLI 2.1.273 with SHA-256
6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1, and
local image ID
sha256:bca9ff191ad16f350ccfff349fcb2b7a8d. The SDK interpreter and image
reference are supplied by Sol's private preflight record. The fresh private
artifact parent must be mode 0700 and its experiment child must not exist.
Keep all resolved paths and runtime identifiers private.

In the calling shell, set and export all three variables from that fresh
preflight before invoking Docker. The guards intentionally fail before the
harness if a variable is empty. The command is bounded to 900 seconds and
stores stdout/stderr only beneath the private artifact parent:

    test -n "$PROBE_SDK_PYTHON" || { echo 'PROBE_SDK_PYTHON is required' >&2; exit 2; }
    test -n "$PROBE_PRIVATE_PARENT" || { echo 'PROBE_PRIVATE_PARENT is required' >&2; exit 2; }
    test -n "$PROBE_IMAGE" || { echo 'PROBE_IMAGE is required' >&2; exit 2; }
    export PROBE_SDK_PYTHON PROBE_PRIVATE_PARENT PROBE_IMAGE
    docker exec -w "$(git rev-parse --show-toplevel)" \
      -e PROBE_SDK_PYTHON="$PROBE_SDK_PYTHON" \
      -e PROBE_PRIVATE_PARENT="$PROBE_PRIVATE_PARENT" \
      -e PROBE_IMAGE="$PROBE_IMAGE" \
      py-bench /bin/bash -c '
        set -euo pipefail
        test -d "$PROBE_PRIVATE_PARENT"
        test "$(stat -c %a "$PROBE_PRIVATE_PARENT")" = 700
        test ! -e "$PROBE_PRIVATE_PARENT/experiment"
        test "$(docker image inspect --format "{{.Id}}" "$PROBE_IMAGE")" = "sha256:bca9ff191ad16f350ccfff349fcb2b7a8d"
        test "$(sha256sum tests/probes/managed_two_domain.py | cut -d " " -f1)" = "c5c183cb215ecf56f3ff028dd2e4175364a1d7f2720df6fcff29e9baadc7cdac"
        test "$(sha256sum tests/probes/managed_native_loopback.py | cut -d " " -f1)" = "4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695"
        test "$(sha256sum tests/test_lane_managed_loopback_probe.py | cut -d " " -f1)" = "3f7c5f63af5331d7bdc4116b04535bc6f549bb852b05a68cef318b115ab9e1ac"
        umask 077
        /usr/bin/timeout --signal=TERM --kill-after=20s 900s \
          /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/tmp CLAUDE_CONFIG_DIR=/tmp \
          python3 tests/probes/managed_two_domain.py \
            --sdk-python "$PROBE_SDK_PYTHON" --image "$PROBE_IMAGE" \
            --private-artifacts "$PROBE_PRIVATE_PARENT/experiment" --explicit-release \
            > "$PROBE_PRIVATE_PARENT/stdout.json" \
            2> "$PROBE_PRIVATE_PARENT/stderr.log"
      '

The bounded command above exited 2 with INCONCLUSIVE. The source container
was created but never started: independent inspect evidence showed
Created/Running=false/Pid=0 and Docker's exact unset-time sentinel
`0001-01-01T00:00:00Z` for both start and finish. The inspected
HostConfig.Tmpfs map named exactly /tmp and /opt/loopback, but the validator
required those tmpfs destinations to appear as active entries in Mounts and
raised two-domain tmpfs destination mismatch. The container Mounts listed only
the writable /opt/state engine volume. No SDK process, source history, release,
target, or negative arm ran. The positive arm reason was
effect-or-observer-uncertain; the negative arm was NOT RUN.

Quarantine also refused to remove the created-but-never-started container
because it required a die event, yielding quarantine-die-event-unconfirmed.
The container and its source-state volume were preserved; no cleanup or retry
occurred. Engine inventory contains three labelled source-state volumes in
total, including this run's volume, and one run-labelled Created source
container. The two volumes from earlier attempts remain untouched. This is an
INCONCLUSIVE diagnostic result, not a Bite 5 verdict. At that checkpoint no
fourth full runtime was authorized; a later one-run authorization is recorded
in the next section.

Private evidence SHA-256 values: abort ledger
ff62f4fa6026ef1bf3af4cf5af5b5bcacb322e809ce7c198265770e25ce50388,
quarantine summary
8c55e5d370934f22c612fb5e0cb126a023979349f131fcce551c3173c6c1848e,
sanitized report
e95ab2c945d6048cc454b32f0d949d8d65082ea65cf633c321e311289d6419cc,
stdout
34eea213ed27b67ee5ecf99a7dc1162e6fa6e35b2308a66265a8f6417c2a022d,
and empty stderr
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.
The frozen T034 runtime hashes remain harness
c5c183cb215ecf56f3ff028dd2e4175364a1d7f2720df6fcff29e9baadc7cdac, helper
4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695, and
tests 3f7c5f63af5331d7bdc4116b04535bc6f549bb852b05a68cef318b115ab9e1ac.
Keep raw IDs and private paths only in Sol's restricted evidence record.

If any precondition or hash check fails, do not invoke the harness. This is
one authorized run, not permission to retry an uncertain effect. This exact
command has been used once; do not repeat it. If it stops
or reports uncertainty, preserve all artifacts and run-owned resources for
review; do not clean up, retry, or proceed to a Bite 5 verdict without the
required evidence review.

## Fourth full Bite 4 attempt — INCONCLUSIVE; authorization consumed

The user has now explicitly authorized exactly one new full Bite 4 attempt
after T035's architecture review and offline gate passed. This is a new run,
not a retry of any historical command. Preserve all three previous
`source-state` volumes and the run-labelled Created source container exactly
as they are; do not inspect them through a writable mount, relabel, reuse, or
clean them up. Astra and Sol's fresh read-only preflight passed. Sol verified a
fresh mode-0700 private artifact parent with its `experiment/` child absent, a
fresh SDK interpreter value, the verified local image reference, and exact
frozen file hashes. The selected
runtime is SDK 0.2.153, bundled CLI 2.1.273 (SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`), and
image ID `sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`.
Keep actual interpreter and private-parent paths only in Sol's private record.

Preflight confirmed the three previous source-state volumes had zero running
attachments. The newest old volume remained RW-referenced by the preserved
never-started Created source container; the first two old volumes were
unattached. This attempt used a separate fresh volume and run identity.

Use exactly the T035-frozen harness, helper, and test files below. In the
calling shell, fill these three variables from the fresh read-only preflight
and export them before `docker exec`; the command refuses to begin with an
unset value. It enforces a new experiment directory, image ID and file hashes
before the harness. The harness is bounded to 900 seconds, with stdout and
stderr redirected only inside the private parent:

```sh
: "${PROBE_SDK_PYTHON:?Set from Sol's fresh SDK 0.2.153 preflight}"
: "${PROBE_PRIVATE_PARENT:?Set to Sol's fresh mode-0700 private parent}"
: "${PROBE_IMAGE:?Set to the verified local image reference}"
export PROBE_SDK_PYTHON PROBE_PRIVATE_PARENT PROBE_IMAGE

docker exec -w "$(git rev-parse --show-toplevel)" \
  -e PROBE_SDK_PYTHON="$PROBE_SDK_PYTHON" \
  -e PROBE_PRIVATE_PARENT="$PROBE_PRIVATE_PARENT" \
  -e PROBE_IMAGE="$PROBE_IMAGE" \
  py-bench /bin/bash -c '
    set -euo pipefail
    test -d "$PROBE_PRIVATE_PARENT"
    test "$(stat -c %a "$PROBE_PRIVATE_PARENT")" = 700
    test ! -e "$PROBE_PRIVATE_PARENT/experiment"
    test "$(docker image inspect --format "{{.Id}}" "$PROBE_IMAGE")" = "sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d"
    printf "%s  %s\n" \
      "cb026d5e31ec7e619934b0bbba28e9f2a7ccad124c20c06b07938d6c7f9ec0dd" tests/probes/managed_two_domain.py \
      "efac7b5ead8a9e61061058b55fba9679b8d6a926e8874118cea06401b9b71ea5" tests/probes/managed_native_loopback.py \
      "f89b12b6a5906a4627c07f2fd5142d424ed46a16c9b74bd48a8ff30b5068f11b" tests/test_lane_managed_loopback_probe.py \
      | sha256sum --check --strict -
    umask 077
    /usr/bin/timeout --signal=TERM --kill-after=20s 900s \
      /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/tmp CLAUDE_CONFIG_DIR=/tmp \
      python3 tests/probes/managed_two_domain.py \
        --sdk-python "$PROBE_SDK_PYTHON" --image "$PROBE_IMAGE" \
        --private-artifacts "$PROBE_PRIVATE_PARENT/experiment" --explicit-release \
        > "$PROBE_PRIVATE_PARENT/stdout.json" \
        2> "$PROBE_PRIVATE_PARENT/stderr.log"
  '
```

Sol ran the command once within the 900-second bound. It exited 2 with
INCONCLUSIVE after the source container start. The first post-start
`validate_two_domain_isolation` in `_install_observer_files` rejected Docker
inspect `Mounts` for omitting active `/tmp` and `/opt/loopback` tmpfs entries,
although `HostConfig.Tmpfs` contained exactly those two configured paths. No
container `exec` action ran: no CLI or probe copy, SDK process, history, release,
target, or negative arm. The positive arm reported
`effect-or-observer-uncertain`, `release_candidate_ready=false`,
`cleanup_complete=false`, `observer_complete=false`, and
`quarantine-container-preserved-for-custody-review`.

Quarantine stopped the new source container and preserved it in Exited 137
state with its attached new `source-state` volume. The prior three volumes and
the older Created source container were left untouched: the first two volumes
remain unattached, while the third remains RW-referenced by that Created
container. Current inventory is four
`source-state` volumes, two source containers (one Created, one Exited 137),
and zero running containers. No resource was removed; no cleanup or retry
occurred. No fifth attempt is authorized. The result is Bite 4 INCONCLUSIVE,
not a Bite 5 verdict; production remains unsupported.

Astra confirms fail-closed behavior is correct: missing active Mounts evidence
does not prove tmpfs is absent. A future producer must provide exact-container
mountinfo or a reviewed trusted pre-SDK attestation. Do not silently relax the
validator. Preserve all four volumes and both containers. This one-run
authorization is consumed; do not replay an uncertain effect, clean up, or
start another attempt. Bite 5 remains a separate pending evidence decision.

Private artifact SHA-256 values: stdout
`2b09daf7efac84ba5386ab5578cfe14da3ec76bc1ddc415fc4d9835180dffc4c`, empty
stderr `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
abort `7a1c95d9bfb92cd3cf427f495626c6d39cd7e0a60043b3742db7c8a93e07ca8b`,
quarantine summary `f44acfbe54965a6bc8a2f15ee186122ceced3a19c7286d014e11f6e0c505338a`,
stop `635884ddb9445b6bc297e9ba1967b75b3097f9fafecf0be5a7fbc96ffb5ab79a`,
manifest `8bd8faa64245210d6c8a7cd2ac801e0798a300852f87a51f25aa640fd931cb80`,
and sanitized report `45a92030725db92a51c3f84b92ebd97561b8b7e2b40d8117f1162ca92a7c82f0`.
Raw IDs and private paths stay in Sol's private evidence record. Frozen T035
code/test hashes remain unchanged.

## Fourth-run diagnosis and T036/T037 closure — historical checkpoint

The fourth run failed because the running-container validator treats top-level
Docker `Mounts` as the active tmpfs witness. T035 only accepts
`HostConfig.Tmpfs` without active `Mounts` for a corroborated never-started
`Created` container; it did not change the running-state rule at
`tests/probes/managed_native_loopback.py:3538-3544`. The fourth inspect showed
exact configured `/tmp` and `/opt/loopback` entries in `HostConfig.Tmpfs` but
no tmpfs entries in `Mounts`, so active presence is unproven, not disproven.
The [Docker CLI issue #3974](https://github.com/docker/cli/issues/3974)
documents the distinct `HostConfig.Tmpfs` and top-level `Mounts` fields. The
frozen harness therefore fails at the first post-start validation before any
container `exec`. That same validation/start path serves source, helper, and
target roles; only the source role was reached in the fourth run.

T036 and T037 are implemented, reviewed, and offline verified. T036 adds a
trusted, bounded `/proc/self/mountinfo` startup wrapper for source, every
helper, and target. It binds two fresh challenge/response captures to the
exact inspect identity and independent engine create/start evidence before any
upload and again before SDK/helper work. Its parser checks the configured
tmpfs destinations, effective mount and superblock flags, exact sizes,
ancestors, duplicates, and bounded complete records. Malformed or uncertain
evidence remains INCONCLUSIVE; an unsafe policy finding becomes FAIL only
after exact identity/event binding and durable capture. T037 preserves volumes
on failure or inconclusive outcomes, including uncertain observer and custody
paths. Astra's targeted reviews passed, and Sol's combined selector passed 110
tests. Frozen hashes and limits are in `verification.md`.

At the pre-sixth checkpoint, the source SDK, history, custody, release, target,
and startup phases remained unobserved; all five attempts then completed were
INCONCLUSIVE and none reached target launch. The Bite 3 production producer is
still absent. At that checkpoint, five source-state volumes and three stopped
source containers were preserved; the sixth-run authorization, reviews,
preflight, and syntax check were complete but root GO remained required. The
sixth result is recorded later in its run section; no cleanup of old resources
is authorized.
Bite 5 remains pending, and production remains unsupported.

## Fifth full Bite 4 attempt — INCONCLUSIVE before source start

The user authorized exactly one fifth bounded attempt after T036/T037 review,
the combined offline gate, and fresh preflight. Sol executed the distinct
hash-guarded command once; it exited 2 / INCONCLUSIVE before source start.
Sol's preflight confirmed SDK 0.2.153, selected bundled CLI 2.1.273 with
SHA-256 `6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`,
and local image ID
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`.
The fresh private parent was mode 0700 with no `experiment/` child. The exact
interpreter and private parent values remain in Sol's restricted preflight
record; do not copy host-specific paths or runtime identifiers here. This
authorization is consumed. Sol High remains the sole runtime executor.

The command below is retained as the exact historical fifth invocation; its
authorization is consumed. Do not rerun it. Before that invocation, its guards
checked the fresh parent, immutable image identity, all three frozen
source/test hashes, SDK version, and the digest of the SDK-selected bundled
CLI. The CLI guard called the existing side-effect-free selector and printed
neither its private path nor runtime identifiers. The harness was bounded to
900 seconds, with stdout and stderr redirected under the private parent:

```sh
: "${PROBE_SDK_PYTHON:?Set from Sol final SDK 0.2.153 preflight}"
: "${PROBE_PRIVATE_PARENT:?Set to Sol fresh mode-0700 private parent}"
: "${PROBE_IMAGE:?Set to Sol verified local image reference}"
export PROBE_SDK_PYTHON PROBE_PRIVATE_PARENT PROBE_IMAGE

docker exec -w "$(git rev-parse --show-toplevel)" \
  -e PROBE_SDK_PYTHON="$PROBE_SDK_PYTHON" \
  -e PROBE_PRIVATE_PARENT="$PROBE_PRIVATE_PARENT" \
  -e PROBE_IMAGE="$PROBE_IMAGE" \
  py-bench /bin/bash -c '
    set -euo pipefail
    test -d "$PROBE_PRIVATE_PARENT"
    test "$(stat -c %a "$PROBE_PRIVATE_PARENT")" = 700
    test ! -e "$PROBE_PRIVATE_PARENT/experiment"
    test "$(docker image inspect --format "{{.Id}}" "$PROBE_IMAGE")" = "sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d"
    printf "%s  %s\n" \
      "6a459bbf647f1d4bca463cc0c3eadfe7c377fe955c8059deeaea032fc9fbdb5f" tests/probes/managed_two_domain.py \
      "e8b876e7322579067fb0903513fc33358c496d110c3bcaf25cb481b440979287" tests/probes/managed_native_loopback.py \
      "faccfdd533d39c5f91730446320e2b9f8850850d295b7f4d20c6b495922dbfce" tests/test_lane_managed_loopback_probe.py \
      | sha256sum --check --strict -
    python3 - "$PROBE_SDK_PYTHON" <<PY
import sys
sys.path.insert(0, "tests/probes")
import managed_native_loopback as probe
selected = probe._select_runtime(sys.argv[1])
if (selected.get("sdk_version") != "0.2.153"
        or selected.get("cli_sha256") != "6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1"):
    raise SystemExit("selected SDK/CLI pin mismatch")
PY
    umask 077
    /usr/bin/timeout --signal=TERM --kill-after=20s 900s \
      /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/tmp CLAUDE_CONFIG_DIR=/tmp \
      python3 tests/probes/managed_two_domain.py \
        --sdk-python "$PROBE_SDK_PYTHON" --image "$PROBE_IMAGE" \
        --private-artifacts "$PROBE_PRIVATE_PARENT/experiment" --explicit-release \
        > "$PROBE_PRIVATE_PARENT/stdout.json" \
        2> "$PROBE_PRIVATE_PARENT/stderr.log"
  '
```

The source container was created but never started. Its inspect record had the
expected immutable image, Entrypoint, complete Cmd/wrapper digest,
`OpenStdin=true`, `AttachStdin=true`, and `Tty=false`; it also reported
`StdinOnce=true`, while the frozen wrapper validator required false. This
deterministic wrapper-configuration mismatch raised the then-generic
`two-domain container image identity mismatch`; the future-only T038
correction makes the stdio profile exact and the diagnostic specific. The
positive arm was INCONCLUSIVE with reason `effect-or-observer-uncertain` and
`quarantine-created-never-started-preserved`; release-candidate,
observer-complete, and cleanup-complete were false. The negative arm was not
run. No witness wrapper, SDK, history, custody, release, or target ran.

Quarantine preserved the new Created source container and its RW-attached
source-state volume. The prior four volumes and two containers were unchanged.
Current inventory is five labelled source-state volumes and three stopped
source containers (two Created, one Exited 137), with zero running. No
resource was removed; no retry or cleanup occurred. This result is not a Bite
5 verdict. The separately authorized sixth attempt has since run; its result
and artifact hashes are recorded in the following sixth-run section.

Private SHA-256 values: sanitized report
`891ae8b9c63a12655ea1b75b8179b024a1dc527111f33476ac659c512ebab731`, stdout
`94aae106ea4c43b392f482c31d2f8a221134f5590df07937cee1d85ee6361d25`, empty
stderr `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
arm-abort `cbbc3da6fbcfb029c02c48c035cb1f075b179fc191bc28221a1a165bb9d5112f`,
quarantine summary `f8938b474684fb1d79c32c92b87ac26d008f1534d61df4d1ba1757570092e209`,
and run manifest
`64eda612e32e0f8d2ba72c640b385f4d30a88c4ceb55812e6b3c6e11c74ea1aa`.
Raw paths and IDs remain private. The run used frozen T036 hashes listed in
`verification.md`; they are historical and do not identify the T038 candidate.

## Sixth full Bite 4 attempt — INCONCLUSIVE; authorization consumed

The user authorized exactly one sixth bounded full Bite 4 attempt after the
T038 correction. Astra's T038 code/test review passed; Sol's focused offline
gate passed 127 tests (2,293 deselected); and Sol's sixth read-only preflight
and py-bench visibility guard passed. Sol ran the sixth attempt once. It ended
INCONCLUSIVE; its authorization is consumed. At that checkpoint, no seventh
full Bite 4 attempt had been authorized.
Preserve the earlier five source-state volumes and three stopped source
containers. Sol's exact outer and nested shell syntax review passed with
`bash -n`; the outer-block SHA-256 is
`29b64b76dd70659b5db62ddfb7227508f2579ca14f276df3d898fe7624bfb08a`, and the
nested-body SHA-256 is
`97a4d5a7e849dcb0bbef1624fe78d5cc6407c68e9da0e9ead972962b371f861f`. Root
Root GO was issued before Sol's single invocation. Do not replay the command
or clean any prior resource.

Frozen T038 SHA-256 values:

- Harness: `tests/probes/managed_two_domain.py` —
  `9f8a71fe30e370e6569bf7db2ec2466cb9338ca8aa89a001f39215a32f1de28c`
- Helper: `tests/probes/managed_native_loopback.py` —
  `7454e747791ddfb45f9d506b1a2999d6df5f4c714dcb064cf7be0dffb8db9d22`
- Tests: `tests/test_lane_managed_loopback_probe.py` —
  `c143d192c9efcbb1e7dc9591047f8307ba87cd9abdec35e7ed82df1a08154fea`

Preflight pins are SDK `0.2.153`, bundled CLI `2.1.273` with SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`, image
`py-bench:brett` with immutable ID
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`,
and Docker client/daemon `29.8.1/29.6.2`. The fresh private artifact parent is
mode 0700; `experiment/` is absent; `exact-inputs.json` is mode 0600 with SHA-256
`fdbc05ff2ac357deffc3c420242c8dd70a3602dba565757ef9cc9a5850ac5fa2`. Its
machine-specific path and the pinned interpreter path stay in Sol's private
preflight record. Five existing labelled volumes and three stopped source
containers were inventoried, with zero running attachments and no unexpected
resources; do not use those old objects as this run's inputs.

In the caller shell, populate these variables from Sol's fresh private
preflight record and export them. The guards refuse empty values before
Docker is invoked. The nested command checks the private-parent mode, absent
experiment child, exact-input record, immutable image, all three frozen file
hashes, and selected SDK/CLI pins. It uses the 900-second limit with a
20-second TERM-to-KILL bound and redirects stdout/stderr only into the private
parent. Sol's `bash -n` review passed for the outer block and nested
`/bin/bash -c` body; their exact hashes are recorded below. Root GO was issued
for this one run. Record its result below after Sol reports it; do not replay
the command or clean prior resources.

```sh
: "${PROBE_SDK_PYTHON:?Set from Sol fresh SDK 0.2.153 preflight}"
: "${PROBE_PRIVATE_PARENT:?Set to Sol fresh mode-0700 private parent}"
: "${PROBE_IMAGE:?Set to the verified local image reference}"
export PROBE_SDK_PYTHON PROBE_PRIVATE_PARENT PROBE_IMAGE

docker exec -w "$(git rev-parse --show-toplevel)" \
  -e PROBE_SDK_PYTHON="$PROBE_SDK_PYTHON" \
  -e PROBE_PRIVATE_PARENT="$PROBE_PRIVATE_PARENT" \
  -e PROBE_IMAGE="$PROBE_IMAGE" \
  py-bench /bin/bash -c '
    set -euo pipefail
    test -d "$PROBE_PRIVATE_PARENT"
    test "$(stat -c %a "$PROBE_PRIVATE_PARENT")" = 700
    test ! -e "$PROBE_PRIVATE_PARENT/experiment"
    test "$(stat -c %a "$PROBE_PRIVATE_PARENT/exact-inputs.json")" = 600
    test "$(sha256sum "$PROBE_PRIVATE_PARENT/exact-inputs.json" | cut -d " " -f1)" = "fdbc05ff2ac357deffc3c420242c8dd70a3602dba565757ef9cc9a5850ac5fa2"
    test -x "$PROBE_SDK_PYTHON"
    test "$(docker image inspect --format "{{.Id}}" "$PROBE_IMAGE")" = "sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d"
    printf "%s  %s\n" \
      "9f8a71fe30e370e6569bf7db2ec2466cb9338ca8aa89a001f39215a32f1de28c" tests/probes/managed_two_domain.py \
      "7454e747791ddfb45f9d506b1a2999d6df5f4c714dcb064cf7be0dffb8db9d22" tests/probes/managed_native_loopback.py \
      "c143d192c9efcbb1e7dc9591047f8307ba87cd9abdec35e7ed82df1a08154fea" tests/test_lane_managed_loopback_probe.py \
      | sha256sum --check --strict -
    python3 - "$PROBE_SDK_PYTHON" <<PY
import sys
sys.path.insert(0, "tests/probes")
import managed_native_loopback as probe
selected = probe._select_runtime(sys.argv[1])
if (selected.get("sdk_version") != "0.2.153"
        or selected.get("cli_sha256") != "6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1"):
    raise SystemExit("selected SDK/CLI pin mismatch")
PY
    umask 077
    /usr/bin/timeout --signal=TERM --kill-after=20s 900s \
      /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/tmp CLAUDE_CONFIG_DIR=/tmp \
      python3 tests/probes/managed_two_domain.py \
        --sdk-python "$PROBE_SDK_PYTHON" --image "$PROBE_IMAGE" \
        --private-artifacts "$PROBE_PRIVATE_PARENT/experiment" --explicit-release \
        > "$PROBE_PRIVATE_PARENT/stdout.json" \
        2> "$PROBE_PRIVATE_PARENT/stderr.log"
  '
```

The bounded invocation exited 2 with `INCONCLUSIVE`. Its positive arm ended
`effect-or-observer-uncertain` and
`quarantine-container-preserved-for-custody-review`; the negative arm did not
run (`positive-release-candidate-not-established`). The source SDK phase
returned, and the observer recorded source running, then stop/removal with
ledgered intents. Only after source removal did the harness create the
target-state volume. The first custody COPY helper failed while producing
`_manifest_summary(args.source)`: Docker exec exited 1 with
`RuntimeError: two-domain file size limit exceeded` at the current 64 KiB per-
file bound. The failure occurred before copy verification, pre-release history
custody, durable release, target-container creation/start, or the negative arm.

Quarantine stopped and preserved the copy helper. Two new volumes (source and
target state) and one Exited helper were retained; zero containers are
running. Aggregate inventory is seven engine volumes (six source-state, one
target-state) and four stopped containers (two Created, two Exited). No
cleanup or retry occurred. Bite 4 remains INCONCLUSIVE, Bite 5 remains pending,
and production remains unsupported. The diagnostic does not establish the
Bite 3 production producer.

Private SHA-256 values: report
`2cca888a2b65170087c500432a7c7a6c26eacdd58509dff3774b8c0ae05db84d`, stdout
`ccc773ab9cbc36157388e32d232cbe2b4305be249082d81ab900c92ec9d3eb9d`, empty
stderr `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
abort ledger `d0e98156493112d2b17642c5fee39cc41efb46f3bcaf4b315ffe22a0147d6121`,
and run artifact manifest
`7711540cb5e09a7f5ccb4be6e61658624ba4086efde827ddbdb93c0902e2e25e`. The
manifest covers 16 files; Sol independently matched them and confirmed
mode-0600 permissions. Paths and raw runtime IDs remain private.

## T040 source-volume metadata diagnostic — bounded stat-only PASS

Sol executed the separately authorized one-shot diagnostic against the sixth
attempt's preserved **source-state** volume. Its container exited 0 after
creating and starting exactly one new diagnostic container with the selected
volume mounted read-only at `/evidence`. The scanner reported nine files and
14 directories totaling 394,590 bytes; the largest and only identified
over-64-KiB config file was a `.json` of 306,896 bytes. It read no file
contents. No target-state volume was mounted, no SDK/runtime was run, and no
custody, release, or Bite 5 decision was established. The diagnostic
container and artifacts remain preserved; its read-only attachment changed
the source volume's engine attachment metadata but not its contents.

Private result SHA-256: artifact manifest
`aa3c4c235afa931507b6dedd28939e43e97c1cd212901c48c7d2150ec016499d`, public
JSON `af7b84e3145e6596044d767c164ca0ddec573ae25c93a1d2ba886de96f22ab68`, and
private JSON `c0f0b0a74d970562782cff6106aeb29fdf1d4b6768d70798c2e34a65df29e0f2`.
Exact paths, names and raw IDs remain private. Current inventory is seven
engine volumes and five stopped containers, zero running. No cleanup occurred.

The read identified why the sixth COPY helper exceeded its 64 KiB per-file
fixture-tree budget. It does not retry that helper or prove a history
mismatch. T041 separates complete fixture-tree manifest/copy/custody from the
history evidence bounds: 512 KiB per file and 2 MiB per tree, while retaining
the 64 KiB history-prefix limit and 512 KiB history-discovery limit. T041's
review and focused offline gate passed. The user authorized one seventh full
Bite 4 attempt after this correction, review, offline gate, and fresh preflight.
The preflight passed; exact-command review and parent GO remain.

Scanner: [`tests/probes/inspect_two_domain_volume_metadata.py`](../../tests/probes/inspect_two_domain_volume_metadata.py).
File SHA-256 is
`fbff3be87a288501d64d977e91d37ba01f5bb43ad596e211e1ca691ea9f81c39`;
the exact source string placed in Docker `Config.Cmd` (with trailing newline
removed by shell command substitution) has SHA-256
`abbe57cc78fdfe4b613df7c421af8447b10fa00bd4edd4ff0c21c4f3029dc683`.
The new offline test module is
[`tests/test_two_domain_metadata_diagnostic.py`](../../tests/test_two_domain_metadata_diagnostic.py).
The scanner's focused offline gate passed 14 tests (2,420 deselected). Astra's
architecture review, Sol's command review, and a fresh read-only preflight
passed before the one authorized execution. The scanner
traverses from
an opened `/evidence` directory fd with no-follow opens, reads no file bytes,
and revalidates file and directory metadata before reporting. Its bounds are
128 regular files, 512 total entries, depth 12, 4,096 encoded bytes per
relative path, an 8-second monotonic scan deadline checked during traversal,
each file/directory revalidation, summary construction, and JSON
serialization, and 64 KiB total JSON output. It refuses links, non-regular
entries, mutation, or exceeded
structural/time/output bounds. A 65,536-byte file, any larger file, or large
aggregate size is reported as metadata and is **not by itself a refusal**.
Private output has relative paths and sizes; `--public-from` emits only
validated counts, byte totals, categories, and path/metadata digests. A refusal
is diagnostic `inconclusive`, not Bite 4 `FAIL`.

The original command passed Astra's architecture review, Sol's scanner-only
offline gate (14 tests), outer/nested shell checks, six Python heredoc parses,
and a read-only preflight. Its prelaunch image guard refused before any Docker
create or source read because the previous immutable image was unavailable.
The replacement image is the one used by the running `py-bench` control
container and supports the stdlib-only metadata scanner. The former sterile
SDK interpreter path is absent, but Sol confirmed a project-private venv is
visible in the control container and selects SDK 0.2.153 with CLI 2.1.273 at
the pinned digest. Those prerequisites remain available locally and must be
freshly pinned before any full Bite 4 run.

The first two authorized invocations failed before any metadata-container
create or source-volume content read. The first symptom appeared as a missing
private prefix in the nested shell. In the second staged-inline attempt, the
outer shell expanded `$PROBE_METADATA_SCRIPT` before staging. Sol confirmed
the common cause: the `PROBE_SOURCE_RUN_ID` parameter-expansion error word
contained an apostrophe in “that volume's sixth run label.” Bash treated it as
an opening single quote despite the surrounding double quotes; later heredoc
text made `bash -n` appear successful. A source-volume metadata inspection may
have been invoked, but no file content was read and no scanner ran. This was a
shell-quoting fault, not a Docker stdin or shared-path finding.

The replacement keeps orchestration as the repository file
[`tests/probes/run_two_domain_volume_metadata.sh`](../../tests/probes/run_two_domain_volume_metadata.sh), SHA-256
`d2d2fba6f32426106ac58effe60f7bb0d12c50ea0d23297093eb7f9f4d13674d`. The caller checks that exact file and the container repeats its
hash and stat-identity checks through the shared worktree. No executable source
is generated or sent through a heredoc, `bash -c`, `eval`, or Docker stdin. The
script validates the pinned image ID, scanner hash, source volume identity,
private parent and exact writable `META_DIR`; it writes and verifies the
private prefix sentinel before its first Docker create. Its existing
read-only isolation profile and bounded create, attach, stop, and post-check
logic remain unchanged. The runner was invoked once after this correction;
preserve both failed pre-effect artifacts and the successful run's artifacts.
Their private details remain outside this runbook.

A pre-run read-only preflight verified seven labelled volumes, four stopped
containers, zero running attachments, and the selected sixth-run source
volume's expected local driver, labels, and options. Private IDs, volume names,
and artifact paths remain in Sol's restricted record; do not substitute another
source volume. The exact command passed review and preflight, using a fresh
shared mode-0700 parent with an absent `metadata/` child. It performed
repository hashing, Docker inspection, and public projection inside
`py-bench`. The source volume contents remain preserved; the read-only reader
changed its engine attachment metadata while attached.

From the feature worktree, export the private values supplied by fresh
preflight. Keep stdout and stderr private. The wrapper below checks the pinned
runner SHA on the caller, verifies the same file identity and SHA inside
`py-bench`, passes a clean environment, and gives the process no stdin. It does
not create the metadata container until the script's prefix sentinel has been
verified.

```sh
set -euo pipefail
umask 077
: "${PROBE_METADATA_PARENT:?Set PROBE_METADATA_PARENT from private preflight}"
: "${PROBE_METADATA_ID:?Set PROBE_METADATA_ID from private preflight}"
: "${PROBE_SOURCE_VOLUME:?Set PROBE_SOURCE_VOLUME from private inventory}"
: "${PROBE_SOURCE_RUN_ID:?Set PROBE_SOURCE_RUN_ID from private inventory}"
: "${PROBE_IMAGE:?Set PROBE_IMAGE to the pinned metadata image ID}"
test "$PROBE_IMAGE" = "sha256:a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094"
case "$PROBE_METADATA_PARENT" in /*) ;; *) exit 2 ;; esac
case "$PROBE_METADATA_ID" in ''|*[!0-9a-f]*) exit 2 ;; esac
test "${#PROBE_METADATA_ID}" = 32
export PROBE_METADATA_PARENT PROBE_METADATA_ID PROBE_SOURCE_VOLUME PROBE_SOURCE_RUN_ID PROBE_IMAGE

PROBE_METADATA_RUNNER="$(realpath -e tests/probes/run_two_domain_volume_metadata.sh)"
test -f "$PROBE_METADATA_RUNNER" && test ! -L "$PROBE_METADATA_RUNNER"
test "$(stat -c %a "$PROBE_METADATA_RUNNER")" = 644
PROBE_METADATA_RUNNER_SHA256="$(sha256sum "$PROBE_METADATA_RUNNER" | cut -d ' ' -f1)"
test "$PROBE_METADATA_RUNNER_SHA256" = "d2d2fba6f32426106ac58effe60f7bb0d12c50ea0d23297093eb7f9f4d13674d"
PROBE_METADATA_RUNNER_CALLER_STAT="$(stat -c '%d:%i:%u:%g:%a:%s' "$PROBE_METADATA_RUNNER")"
test -d "$PROBE_METADATA_PARENT" && test ! -L "$PROBE_METADATA_PARENT"
test "$(realpath -e -- "$PROBE_METADATA_PARENT")" = "$PROBE_METADATA_PARENT"
test "$(stat -c %a "$PROBE_METADATA_PARENT")" = 700
test "$(stat -c %u "$PROBE_METADATA_PARENT")" = "$(id -u)"
test -w "$PROBE_METADATA_PARENT"
PROBE_METADATA_PARENT_CALLER_STAT="$(stat -c '%d:%i:%u:%g:%a' "$PROBE_METADATA_PARENT")"
test ! -e "$PROBE_METADATA_PARENT/metadata" && test ! -L "$PROBE_METADATA_PARENT/metadata"
test ! -e "$PROBE_METADATA_PARENT/runner.stdout" && test ! -L "$PROBE_METADATA_PARENT/runner.stdout"
test ! -e "$PROBE_METADATA_PARENT/runner.stderr" && test ! -L "$PROBE_METADATA_PARENT/runner.stderr"
: > "$PROBE_METADATA_PARENT/runner.stdout"
: > "$PROBE_METADATA_PARENT/runner.stderr"
chmod 600 "$PROBE_METADATA_PARENT/runner.stdout" "$PROBE_METADATA_PARENT/runner.stderr"

docker exec -w "$(git rev-parse --show-toplevel)" \
  -e PROBE_METADATA_PARENT="$PROBE_METADATA_PARENT" \
  -e PROBE_METADATA_ID="$PROBE_METADATA_ID" \
  -e PROBE_SOURCE_VOLUME="$PROBE_SOURCE_VOLUME" \
  -e PROBE_SOURCE_RUN_ID="$PROBE_SOURCE_RUN_ID" \
  -e PROBE_IMAGE="$PROBE_IMAGE" \
  -e PROBE_METADATA_RUNNER="$PROBE_METADATA_RUNNER" \
  -e PROBE_METADATA_RUNNER_SHA256="$PROBE_METADATA_RUNNER_SHA256" \
  -e PROBE_METADATA_RUNNER_CALLER_STAT="$PROBE_METADATA_RUNNER_CALLER_STAT" \
  -e PROBE_METADATA_PARENT_CALLER_STAT="$PROBE_METADATA_PARENT_CALLER_STAT" \
  py-bench /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin \
    PROBE_METADATA_PARENT="$PROBE_METADATA_PARENT" \
    PROBE_METADATA_ID="$PROBE_METADATA_ID" \
    PROBE_SOURCE_VOLUME="$PROBE_SOURCE_VOLUME" \
    PROBE_SOURCE_RUN_ID="$PROBE_SOURCE_RUN_ID" \
    PROBE_IMAGE="$PROBE_IMAGE" \
    PROBE_METADATA_RUNNER="$PROBE_METADATA_RUNNER" \
    PROBE_METADATA_RUNNER_SHA256="$PROBE_METADATA_RUNNER_SHA256" \
    PROBE_METADATA_RUNNER_CALLER_STAT="$PROBE_METADATA_RUNNER_CALLER_STAT" \
    PROBE_METADATA_PARENT_CALLER_STAT="$PROBE_METADATA_PARENT_CALLER_STAT" \
    /bin/bash --noprofile --norc -euo pipefail "$PROBE_METADATA_RUNNER" </dev/null \
    > "$PROBE_METADATA_PARENT/runner.stdout" 2> "$PROBE_METADATA_PARENT/runner.stderr"
```

The wrapper and runner both pass `bash -n`. The populated-variable caller prefix
also passed a no-Docker execution with a fresh temporary mode-0700 parent; it
created only empty mode-0600 capture files and stopped before `docker exec`.
This validates the pre-effect shell guards only, not the cross-container path,
metadata scan, or any Docker behavior.

This was a metadata observation only. The scanner limits its JSON
report to 64 KiB. The outer capture applies a 128 KiB per-file ceiling to the
attached stdout/stderr files and refuses stdout above 64 KiB. A reported file
over 65,536 bytes does not mean its contents were inspected. The fixture-tree
limit correction below keeps the history-prefix protocol at 64 KiB and history
discovery at 512 KiB. Review the private inventory separately; keep the public
record path-free. The selected source volume's file
contents are not changed, but its engine attachment metadata necessarily
changes while the read-only diagnostic container is attached. Bounded,
status-checked container and volume inspections plus pre/post running-attachment
queries bind the retained artifacts to the selected source volume. Those
snapshots do not prove continuous writer exclusion or rule out a concurrent
attachment between checks. No target volume or preserved runtime container is
changed. The diagnostic container and its artifacts are retained for review.
Bite 4 remains INCONCLUSIVE and Bite 5 remains pending. Do not repeat the
diagnostic, remove its container, or clean any preserved resources.

## T041 fixture-tree limit correction — review and offline PASS

Fixture manifest/copy/custody now use a 512 KiB per-file ceiling and 2 MiB
complete-tree ceiling through one shared no-follow traversal. This applies to
source/target manifests, copy verification, pre-release/final custody, and
target prestart. History capture remains capped at 64 KiB, and history
discovery remains capped at 512 KiB. The 306,896-byte config JSON from T040 is
copied and manifested byte-for-byte; final custody still detects its mutable
config contents without losing the identity-linked history prefix.

Astra's targeted architecture review passed. Sol's canonical
`tests/run.sh --parallel-safe -k two_domain` gate passed **144 selected tests,
0 failures/errors/skips in 14.434s**. Frozen hashes:

- Native probe: `a0379e325db46d599d5e3d98c3b25f4200036ae8e08eb1a618d43d59d4f5b069`
- Harness: `9f8a71fe30e370e6569bf7db2ec2466cb9338ca8aa89a001f39215a32f1de28c`
- Focused tests: `fa29dffec7c86131152dcee8b116e02f2a772130177d3d4fb25cb406a915b6b5`

Private gate artifact SHA-256: stdout
`cecc5ecbbd849fe2a7ae66e63728eaf45fbc7a580130c3a553fe472af2283356`, stderr
`e8e31f13e4582ffc1e0a2ce36474cdd0547620d2020024e5c8e9af934dfe9847`, and
JUnit `a4d994ae3288ceb50023edb79e408e22d73954c7664aa2e3f12a4ec0386ff8a8`.
This is offline evidence only. Before the seventh run, Sol's read-only
preflight passed with seven engine volumes, five stopped containers, and zero
running. The seventh attempt and its result are recorded below.

## Seventh full Bite 4 attempt — executed once; INCONCLUSIVE arm, report FAIL

The user authorized one seventh full attempt after the metadata diagnosis,
T041 correction/review, focused offline gate, and fresh preflight. Those
preconditions passed. The selected SDK is 0.2.153; the bundled CLI is 2.1.273
with SHA-256 `6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`.
The image is pinned by immutable ID
`sha256:a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094`.
The fresh parent is mode 0700, its `exact-inputs.json` is mode 0600 with
SHA-256 `a7419bb7e336bfe3410e8335de73aa16bb63ad25159493673ed2f190aefa7755`,
and `experiment/` is absent. Preflight saw seven engine volumes, five stopped
containers, and zero running. No private parent path, runtime ID, volume name,
or interpreter path is recorded here.

The command below is the exact distinct invocation used once. Sol's shell and
command review passed. Its guards checked the fresh private inputs, pinned
image, exact source/test hashes, selected SDK/CLI, mode-0700 parent, and absent
`experiment/` child before starting the 900-second bounded harness. Stdout and
stderr were written only inside the private parent. This command is historical;
its single-use authorization is consumed. Do not replay it or clean resources.

```sh
set -euo pipefail
: "${PROBE_SDK_PYTHON:?Set from the fresh SDK 0.2.153 preflight}"
: "${PROBE_PRIVATE_PARENT:?Set from the fresh mode-0700 preflight}"
: "${PROBE_IMAGE:?Set to the immutable image ID from preflight}"
test "$PROBE_IMAGE" = "sha256:a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094"
export PROBE_SDK_PYTHON PROBE_PRIVATE_PARENT PROBE_IMAGE

docker exec -w "$(git rev-parse --show-toplevel)" \
  -e PROBE_SDK_PYTHON="$PROBE_SDK_PYTHON" \
  -e PROBE_PRIVATE_PARENT="$PROBE_PRIVATE_PARENT" \
  -e PROBE_IMAGE="$PROBE_IMAGE" \
  py-bench /bin/bash -c '
    set -euo pipefail
    test -d "$PROBE_PRIVATE_PARENT" && test ! -L "$PROBE_PRIVATE_PARENT"
    test "$(stat -c %a "$PROBE_PRIVATE_PARENT")" = 700
    test ! -e "$PROBE_PRIVATE_PARENT/experiment"
    test "$(stat -c %a "$PROBE_PRIVATE_PARENT/exact-inputs.json")" = 600
    test "$(sha256sum "$PROBE_PRIVATE_PARENT/exact-inputs.json" | cut -d " " -f1)" = "a7419bb7e336bfe3410e8335de73aa16bb63ad25159493673ed2f190aefa7755"
    test -x "$PROBE_SDK_PYTHON"
    test "$(docker image inspect --format "{{.Id}}" "$PROBE_IMAGE")" = "sha256:a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094"
    printf "%s  %s\n" \
      "9f8a71fe30e370e6569bf7db2ec2466cb9338ca8aa89a001f39215a32f1de28c" tests/probes/managed_two_domain.py \
      "a0379e325db46d599d5e3d98c3b25f4200036ae8e08eb1a618d43d59d4f5b069" tests/probes/managed_native_loopback.py \
      "fa29dffec7c86131152dcee8b116e02f2a772130177d3d4fb25cb406a915b6b5" tests/test_lane_managed_loopback_probe.py \
      | sha256sum --check --strict -
    python3 - "$PROBE_SDK_PYTHON" <<PY
import sys
sys.path.insert(0, "tests/probes")
import managed_native_loopback as probe
selected = probe._select_runtime(sys.argv[1])
if (selected.get("sdk_version") != "0.2.153"
        or selected.get("cli_sha256") != "6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1"):
    raise SystemExit("selected SDK and CLI pin mismatch")
PY
    test ! -e "$PROBE_PRIVATE_PARENT/stdout.json"
    test ! -e "$PROBE_PRIVATE_PARENT/stderr.log"
    umask 077
    /usr/bin/timeout --signal=TERM --kill-after=20s 900s \
      /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/tmp CLAUDE_CONFIG_DIR=/tmp \
      python3 tests/probes/managed_two_domain.py \
        --sdk-python "$PROBE_SDK_PYTHON" --image "$PROBE_IMAGE" \
        --private-artifacts "$PROBE_PRIVATE_PARENT/experiment" --explicit-release \
        > "$PROBE_PRIVATE_PARENT/stdout.json" \
        2> "$PROBE_PRIVATE_PARENT/stderr.log"
  '
```

The outer command exited 1 because the final report sanitizer raised
`private-identifier-in-report`: the full immutable image ID was both in the
private input list (`args.image`) and in the intentional public field
`identities.image_id`. That packaging result is a false-positive FAIL. The
private arm record is INCONCLUSIVE, reason `startup-task-event-observed`.
Source stop/exclusion, exact source-to-target copy, pre-release identity-linked
parent history custody, durable release, target startup/stop/removal, and final
custody were observed. The exact parent UUID matched; there were no observed
parent/child messages, history-read failure, or protocol errors. One native
task event was observed at target startup, so the history query was skipped.
The negative arm did not run. The arm's `release_candidate_ready` was true and
`cleanup_complete` false; this is not a PASS and does not satisfy Bite 3's
source-containment evidence criteria.

The run added two preserved volumes and left no seventh-run container. Current
inventory is nine Bite 4 volumes (seven source-state, two target-state), five
older stopped containers, and zero running containers. No cleanup or eighth
run is authorized. Bite 5 remains pending, production remains unsupported, and
the sanitizer and startup-lifecycle corrections below are future-only changes
that passed review and offline validation, not runtime validation.

Private artifact SHA-256: manifest
`537b3741de9c42e6ba9428f343d22a68e3196556e3755107a0c468f4e756902e`, public
report `3db0840883f58d5dfd88fe727cb29e0df7e8977cd7c126f84ffdffb7dee025e9`,
stdout `e2ef15dee6b3b6884d6d36fb1d237d3ff862be6448a055512650ad683683bbed`, arm
result `6cee6803105e5668c166a340660624d99050e5df292f5c3b939502c2c0df30c5`,
release ledger `44d97078a835f12ddb7931f4e79778ed81a4da34f22df5efd4f71ce1fbd80807`,
and target-launch ledger
`8024b9967ee5f20fc5a103e6b191cc81f91f7c974f0d2e4301266a8e0db4a6f8`. The
37 private artifact files remained mode 0600; their path and runtime IDs stay
in the restricted evidence store.

## Historical eighth full Bite 4 attempt — executed once; INCONCLUSIVE

The user authorized one eighth full attempt after the T043/T044 review and
focused offline gate and the fresh read-only preflight. It ran once using the
distinct command below; its authorization is consumed. The attempt collected
the bounded target-startup task-lifecycle snapshot before the existing sticky
history-query gate. The gate, query decision, and runtime effects remained
unchanged. The result is INCONCLUSIVE; Bite 5 remains pending.

The fresh read-only preflight reserved a mode-0700 private parent with no
`experiment/` child and a mode-0600 `exact-inputs.json` whose SHA-256 is
`9f0dbfb600303d016297ab755b9984f4b1a8c1e2b94e510a2b27759c62cffc0e`. It pinned
SDK 0.2.153, selected CLI 2.1.273 with SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`, and
image ID `sha256:a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094`.
The interpreter and private parent paths remain in the private preflight
record. The command pinned the harness/native/test snapshot below, checked the
SDK/CLI and image pins before effects, and bounded the invocation to 900
seconds with a 20-second kill grace. Stdout and stderr remained in the private
parent.

```sh
set -euo pipefail
: "${PROBE_SDK_PYTHON:?Set from the fresh SDK 0.2.153 preflight}"
: "${PROBE_PRIVATE_PARENT:?Set from the fresh mode-0700 preflight}"
: "${PROBE_IMAGE:?Set to the immutable image ID from preflight}"
test "$PROBE_IMAGE" = "sha256:a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094"
export PROBE_SDK_PYTHON PROBE_PRIVATE_PARENT PROBE_IMAGE

docker exec -w "$(git rev-parse --show-toplevel)" \
  -e PROBE_SDK_PYTHON="$PROBE_SDK_PYTHON" \
  -e PROBE_PRIVATE_PARENT="$PROBE_PRIVATE_PARENT" \
  -e PROBE_IMAGE="$PROBE_IMAGE" \
  py-bench /bin/bash -c '
    set -euo pipefail
    test -d "$PROBE_PRIVATE_PARENT" && test ! -L "$PROBE_PRIVATE_PARENT"
    test "$(stat -c %a "$PROBE_PRIVATE_PARENT")" = 700
    test ! -e "$PROBE_PRIVATE_PARENT/experiment"
    test "$(stat -c %a "$PROBE_PRIVATE_PARENT/exact-inputs.json")" = 600
    test "$(sha256sum "$PROBE_PRIVATE_PARENT/exact-inputs.json" | cut -d " " -f1)" = "9f0dbfb600303d016297ab755b9984f4b1a8c1e2b94e510a2b27759c62cffc0e"
    test -x "$PROBE_SDK_PYTHON"
    test "$(docker image inspect --format "{{.Id}}" "$PROBE_IMAGE")" = "sha256:a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094"
    printf "%s  %s\n" \
      "a3852a6969599c1b605edb60a371069d6de9f41317a9082cd69c0e65ab800c62" tests/probes/managed_two_domain.py \
      "bf7032097ba264aa199e6f0555d4ab4412c85043b0b12e674a8a4461722d78e9" tests/probes/managed_native_loopback.py \
      "c23f6a3d91aafc33dd056b67d89034363c7ba6ecea494389b519b6897fd698fd" tests/test_lane_managed_loopback_probe.py \
      | sha256sum --check --strict -
    python3 - "$PROBE_SDK_PYTHON" <<PY
import sys
sys.path.insert(0, "tests/probes")
import managed_native_loopback as probe
selected = probe._select_runtime(sys.argv[1])
if (selected.get("sdk_version") != "0.2.153"
        or selected.get("cli_sha256") != "6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1"):
    raise SystemExit("selected SDK and CLI pin mismatch")
PY
    test ! -e "$PROBE_PRIVATE_PARENT/stdout.json"
    test ! -e "$PROBE_PRIVATE_PARENT/stderr.log"
    umask 077
    /usr/bin/timeout --signal=TERM --kill-after=20s 900s \
      /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/tmp CLAUDE_CONFIG_DIR=/tmp \
      python3 tests/probes/managed_two_domain.py \
        --sdk-python "$PROBE_SDK_PYTHON" --image "$PROBE_IMAGE" \
        --private-artifacts "$PROBE_PRIVATE_PARENT/experiment" --explicit-release \
        > "$PROBE_PRIVATE_PARENT/stdout.json" \
        2> "$PROBE_PRIVATE_PARENT/stderr.log"
  '
```

The command exited 2 and wrote a public INCONCLUSIVE report; the sanitizer
passed. The positive arm was INCONCLUSIVE with `startup-task-event-observed`,
`observer_complete=true`, `release_candidate_ready=true`, and
`cleanup_complete=false`. The negative arm was NOT RUN. Source stop/exclusion,
exact copy, pre-release identity-linked history custody, durable release,
exact-parent target initialization/start/stop/removal, and final saved-edit and
history custody were observed.

The target/startup snapshot contained one `system/task_notification` with
status `stopped`, `target-observed` sequence 1, and matching session
correlation. Task and agent identity were unknown, source terminal seed was
unavailable, and identity was unresolved; the snapshot remained unknown and
incomplete. No assistant/tool activity, parent/child messages, or gateway
routes were observed. The sticky gate correctly skipped history query. This
does not satisfy Bite 3's PASS criteria and is not a Bite 5 verdict.

The run added two preserved volumes: inventory is now eleven volumes (eight
source-state and three target-state), five prior stopped containers (four
Bite 4 and one metadata diagnostic), zero running, and no eighth-run
containers. No cleanup or retry occurred. The single-use authorization is
consumed; no ninth run or cleanup is authorized. Production remains
unsupported.

Private artifact SHA-256: manifest
`3626f45bdea3b9932b5debbf7e946df7ad7ed5a47a83f552caf47334ba88ddd4`, report
`eba9d0dc0646697af4f453d6881d95d3055d97935a8d53b070ea034cfaee5383`, stdout
`ae51147de5c27869769f49a9e715864f9f3cff3d2be78fff9b36e2d938cfaba3`, arm
result `641242a7fe2625e0b978463d7a3c7aabab4bf3b053378d665e564ae89929be32`,
release ledger
`fcc6faabe0b0446dcf5cef5d763b17b9587c13e74798ed90eaeebd5709246e6c`, and
target-launch ledger
`808af1888b195193807600ad8192c43123888da1d7f1f79a1904e4fc475dfe60`. Raw
paths and runtime IDs remain private. Do not mount preserved volumes for
content inspection, alter them, or clean them; read-only engine inventory
checks remain permitted.

## Ninth full Bite 4 attempt — executed once; INCONCLUSIVE

The one separately authorized ninth attempt ran once and exited 2 with a
sanitized report and `support_claim=false`. The positive arm result was
INCONCLUSIVE with reason `source-native-task-terminal-seed-unavailable`,
`observer_complete=true`, `release_candidate_ready=false`, and
`cleanup_complete=false`. The negative arm was not run; no positive release
candidate was established.

Source stop and removal were observed, along with exact copy,
identity-linked pre-release parent-history custody, and final custody of the
copied volumes. The source parent exited and tracked fixtures were excluded.
Source-container shutdown was harness/engine enforced with exit 137, not
natural graph shutdown or production containment. The source projection
reported an unavailable terminal seed but omitted its detailed reason
envelope, leaving the exact missing identity/event condition unknown. The
target-state volume was copied; no release or target-launch ledger and no
target runtime container were created. Event ledger entries 1–145 precede
public event 146, `final-custody-result-persisted`, which carries the sealed
arm-result digest.

The run added two preserved volumes: 13 total (nine source-state, four
target-state), five older stopped containers (four Bite 4 and one metadata
diagnostic), zero running, and no ninth-run container. No cleanup or retry
occurred. The one-run authorization is consumed; no tenth run or cleanup is
authorized. Available-seed transfer, target fingerprint validation,
correlation/startup/history query, and the negative arm remain unexercised.
Full frozen source, preflight, runtime, custody, event, and artifact hashes are
in `verification.md`. Private paths and raw runtime identifiers remain
restricted.

## Tenth full Bite 4 attempt — executed once; INCONCLUSIVE

The separately authorized tenth invocation ran once and exited 2. Its positive
result was INCONCLUSIVE with reason
`source-native-task-terminal-seed-unavailable`, detailed reason
`terminal-task-hook-evidence-incomplete`. The v2 lifecycle projection had four
complete events: one started task with a tool-use ID; one hook callback was
rejected as `hook-tool-use-id-mismatch`; zero hook callbacks were stored or
joined.

Source stop/removal was harness/engine enforced with exit 137, not natural
graph shutdown. Exact copy, pre-release identity-linked history custody, and
final saved-edit/history-prefix custody were retained. No release or
target-launch ledger, target runtime container, or positive release candidate
was established; the negative arm was not run. The event ledger covers entries
1–145 and event 146 persists the final result with sealed digest
`addefcf9282109879c5fd1eaa74a199eb03949e8b81ed8c13b4728a837db8258`.

Fifteen volumes remain preserved (10 source-state, five target-state), along
with the same five older stopped containers; zero are running and no
tenth-run container remains. No cleanup occurred. Artifact hashes are in
`verification.md`; private py-bench evidence is identified there by bundle
label without a host-absolute path.

Astra's post-run review says the handler's mismatch rejection was correctly
fail-closed. The pinned SDK forwards an optional callback tool ID but does not
guarantee equality with the selected task tool ID. The retained summary lacks
the rejected event kind/digests, so the mismatch cannot be classified as tool
role, task, or association. This does not establish a CLI defect. Any future
investigation should capture bounded rejected-hook event kind/order and
separate callback/input/current-task/session/tool digests, then seek an
authoritative structured bridge. Do not loosen exact equality or infer by
cardinality.

## Historical entry gate — seventh full Bite 4 attempt

This checklist records the entry gate for the seventh full Bite 4 attempt.
The user authorized one attempt after the metadata diagnosis, reviewed fix,
focused offline gate, and fresh preflight. Those gates passed, Sol reviewed the
command, and the attempt ran once as recorded above. The separately authorized
metadata-only diagnostic also completed once; neither command may be repeated.

1. Astra has reviewed the two-domain diagnostic topology in
   [`contracts/source-only-diagnostic.md`](contracts/source-only-diagnostic.md)
   and this runbook. Astra's targeted architecture review of T033's frozen
   observer correction and the future-only T035 correction passed. The first
   six attempts are recorded above and remain INCONCLUSIVE. The seventh attempt
   was authorized after metadata diagnosis, reviewed fix, focused offline gate,
   and fresh preflight. Astra's T038 review, Sol's focused 127-test
   offline gate, sixth read-only preflight, exact shell syntax review, and
   root GO all passed before the sixth run. The prior separate create-only
   smoke is recorded above.
2. The candidate implementation is frozen and has an exact offline-test
   selector and runtime invocation recorded here. The source and target use
   different containers and runtime domains. The external observer and
   custodian run outside both. No target container exists during the source
   phase.
3. The implementation has a distinct topology validator; the existing
   `validate_isolation` stays unchanged. One unique engine-managed fixture
   volume has stable, separately inventoried `config/` (the actual SDK
   history store) and `workspace/` paths. Its bounded no-follow tree reader
   rejects symlinks, non-regular and hard-linked files, path escapes, and
   mutation; fixture manifests permit at most 512 KiB per file and 2 MiB per
   complete tree. These limits do not change the 64 KiB history-prefix bound
   or the 512 KiB history-discovery bound. The deterministic saved edit is
   placed under this persistent workspace before source stop.
4. The implementation atomically persists and fsyncs stop/removal and
   target-launch intents before their effects, and never replays an uncertain
   effect. Explicit release is a selected opt-in input bound to source
   invocation, fixture owner/lineage/runner/daemon identities,
   source-removal observation digest, the unique identity-linked parent
   transcript prefix verified against stopped-source custody and the exact
   copied target tree, a sanitized live engine-inventory digest proving no
   run container or writable helper remains and exactly the two fixture
   volumes remain, source manifest digest, target-spec fingerprint, target
   profile, and exact parent UUID. The target uses the
   exact pinned SDK-selected CLI and existing sticky startup-activity gate.
   Final target custody occurs only after target stop and observed writer
   exclusion.
5. The future-only volume observer correction passed Astra's targeted
   architecture review and Sol's frozen offline selector
   `tests/run.sh --parallel-safe -k two_domain`: **39 passed, 2,293 deselected
   in 9.47s**. It covers actor identity consistency, delayed cross-stream
   mount/unmount evidence, stream health, and bounded timeout as well as the
   existing offline custody and release checks. JUnit SHA-256:
   `91b1b34dc62cf8e34035eea99b6bbdb37b3675518f1585fa469f220be580c6ba`; log
   SHA-256:
   `b62a03373d1fd2950579083ab6275d8b720143e8b7d5f4f9495fa5dcd1ec467e`.
   Tested hashes: harness `1aa5f6f35beea569aa6c4f206cb7dcd08f9ee9d4cdea1bee5bc268ef34cd06b6`,
   helper `4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695`,
   tests `5f5869655cc046674dbd697e3f816fd28ea66e38c0f4a0203225d1695d5e2bca`.
   This verifies only the future-only offline observer repair, not a Bite 4
   runtime observation, the preserved volume, or runtime acceptance. The
   earlier 26-test gate applies to the preceding candidate snapshot. T035's
   exact Created-state/tmpfs/quarantine correction also passed Astra review and
   Sol's 59-test offline selector as recorded above; neither gate is runtime
   acceptance.
6. Sol's sixth fresh read-only preflight passed for SDK 0.2.153, selected CLI
   2.1.273 (SHA-256
   `6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`), and
   local image ID
   `sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`.
   Before the sixth run, it reserved a fresh mode-0700 private parent with no
   `experiment/` child, verified the mode-0600 exact-input record and py-bench
   visibility, and created no runtime object. The interpreter and parent path
   stay private. The image and frozen file hashes are pinned in the command
   above.
7. At seventh-run entry, seven volumes and five stopped containers existed,
   with zero running; that attempt is complete and its authorization consumed.
   At the seventh-run checkpoint inventory was nine volumes and five older
   stopped containers, with zero running. This was a historical checkpoint;
   the eighth attempt and resulting inventory are recorded above. Preserve all
   resources. No ninth full attempt or cleanup is authorized; Bite 5 remains
   pending without a verdict.

If an entry item is missing, the result is **not run**. Do not substitute the
current same-container loopback probe, run `docker pull`, weaken the sticky
startup gate, or improvise a command from old artifacts.

## Historical Bite 4 runtime command — do not repeat

The five commands below record earlier harness invocations and are retained
as historical provenance only. Together with the executed sixth command
above, they are not replay instructions. At that historical checkpoint, no
further run was authorized; a later seventh attempt is separately authorized
only after the listed diagnosis and gates.

Sol's read-only preflight passed in `py-bench`: SDK 0.2.153, selected CLI
2.1.273 with SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`, and
local runtime image `py-bench:brett` resolving to immutable ID
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`.
The sterile SDK interpreter path and private artifact parent are machine-
specific and remain in Sol's private preflight record. Set
`PROBE_SDK_PYTHON` to the preflight-verified 0.2.153 interpreter path and
`PROBE_PRIVATE_PARENT` to the preflight-reserved mode-0700 private directory;
its `experiment/` child must still be absent. From the feature worktree, the
bounded invocation is:

```sh
: "${PROBE_SDK_PYTHON:?Set from Sol's private preflight record}"
: "${PROBE_PRIVATE_PARENT:?Set to the private parent from Sol's preflight record}"
export PROBE_SDK_PYTHON PROBE_PRIVATE_PARENT

docker exec -w "$(git rev-parse --show-toplevel)" \
  -e PROBE_SDK_PYTHON="$PROBE_SDK_PYTHON" \
  -e PROBE_PRIVATE_PARENT="$PROBE_PRIVATE_PARENT" \
  py-bench /bin/bash -c 'umask 077; /usr/bin/timeout --signal=TERM --kill-after=20s 900s /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/tmp CLAUDE_CONFIG_DIR=/tmp python3 tests/probes/managed_two_domain.py --sdk-python "$PROBE_SDK_PYTHON" --image py-bench:brett --private-artifacts "$PROBE_PRIVATE_PARENT/experiment" --explicit-release > "$PROBE_PRIVATE_PARENT/stdout.json" 2> "$PROBE_PRIVATE_PARENT/stderr.log"'
```

The environment variables carried the preflight-resolved interpreter and
private path without publishing machine-specific host paths in this document.
The 900-second timeout was a hard bound; stdout and stderr were private. The
harness created `experiment/` with mode `0700`. Any exact resolved paths belong
only in private execution evidence. Sol's initial outer
command failed before reaching the harness because these variables were not
exported. The corrected invocation above then launched the host harness once,
but it aborted before source startup; no selected SDK runtime experiment
occurred. Read-only diagnosis found the engine create event lacked the custom
labels required by the then label-filtered volume-event stream, while later
volume inspection showed the expected labels. The future-only correction
retains the label-filtered container stream and uses a separate unfiltered
volume-only stream, then independently attests only preregistered names. The
actual invocation is complete; do not repeat it. The preserved volume and
observer gap are detailed in
`live-validation.md`.

## Newly authorized Bite 4 follow-up — executed once; do not repeat

The user authorized one new Bite 4 test after T033. That authorization is
consumed; this section records the exact command and its result. Sol's fresh read-only
preflight passed: SDK `0.2.153`; CLI `2.1.273`, SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`; and
the pinned local image ID
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`.
The exact SDK interpreter, local image reference, and mode-0700 private
artifact parent remain in Sol's private record. The new parent's
`experiment/` child was absent at preflight. Astra's read-only assessment found
no concrete blocker: the earlier uncertainty was volume-event observation
only, no source was stopped or launched, and the preserved old volume had no
attached containers. The follow-up used fresh run identities, volumes, ledger,
and artifacts; keep both preserved volumes untouched.

Use only the frozen corrected candidate hashes below. The command checks them
before starting the harness and verifies that the fresh-preflight local image
reference resolves to the recorded immutable ID. Set all variables in the
calling shell before `docker exec`; machine-specific interpreter and artifact
paths stay private:

```sh
: "${PROBE_SDK_PYTHON:?Set to the fresh-preflight SDK 0.2.153 interpreter}"
: "${PROBE_PRIVATE_PARENT:?Set to Sol's new mode-0700 private artifact parent}"
: "${PROBE_IMAGE:?Set to the local image reference from fresh preflight}"
export PROBE_SDK_PYTHON PROBE_PRIVATE_PARENT PROBE_IMAGE

docker exec -w "$(git rev-parse --show-toplevel)" \
  -e PROBE_SDK_PYTHON="$PROBE_SDK_PYTHON" \
  -e PROBE_PRIVATE_PARENT="$PROBE_PRIVATE_PARENT" \
  -e PROBE_IMAGE="$PROBE_IMAGE" \
  py-bench /bin/bash -c '
    set -euo pipefail
    test -d "$PROBE_PRIVATE_PARENT"
    test "$(stat -c %a "$PROBE_PRIVATE_PARENT")" = 700
    test ! -e "$PROBE_PRIVATE_PARENT/experiment"
    test "$(docker image inspect --format "{{.Id}}" "$PROBE_IMAGE")" = "sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d"
    printf "%s  %s\n" \
      "1aa5f6f35beea569aa6c4f206cb7dcd08f9ee9d4cdea1bee5bc268ef34cd06b6" tests/probes/managed_two_domain.py \
      "4634749f9f42b566baf54bb1f089211792b83b55b43734dfed55a56473813695" tests/probes/managed_native_loopback.py \
      "5f5869655cc046674dbd697e3f816fd28ea66e38c0f4a0203225d1695d5e2bca" tests/test_lane_managed_loopback_probe.py \
      | sha256sum --check --strict -
    umask 077
    /usr/bin/timeout --signal=TERM --kill-after=20s 900s \
      /usr/bin/env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/tmp CLAUDE_CONFIG_DIR=/tmp \
      python3 tests/probes/managed_two_domain.py \
        --sdk-python "$PROBE_SDK_PYTHON" --image "$PROBE_IMAGE" \
        --private-artifacts "$PROBE_PRIVATE_PARENT/experiment" --explicit-release \
        > "$PROBE_PRIVATE_PARENT/stdout.json" \
        2> "$PROBE_PRIVATE_PARENT/stderr.log"
  '
```

This is the historical second full attempt covered by its distinct user
authorization; it has already been executed and exited 2 / INCONCLUSIVE at source-container
creation. The command's hash guards identify the frozen snapshot used for that
run, not Luna's later offline correction candidate. The 900-second timeout
bounded the harness. The corrected observer
saw the source-state volume create, then Docker container creation failed with
exit 125. The exact daemon stderr was not retained. A writable volume-mount
`rw` token is a suspected command-builder cause, not confirmed. No source
runtime/history, release, target, or negative arm ran; zero run-labelled
containers remain and two source-state volumes are preserved. The full result
and artifact digests are in `live-validation.md`. At this historical checkpoint, no cleanup, retry, or third full source/target
runtime was authorized. The later third-attempt authorization is documented
above. The future-only candidate later passed
Astra review and Sol's 41-test offline gate; the separately authorized narrow
create-only smoke is recorded above and does not reopen this historical
command. The
stderr excerpt is capped at 4,096 retained bytes, subprocess capture itself is
unbounded, and timeout/pre-arm failures do not use the capture path. Bite 5
remains pending; no verdict has been made.

## Bite 4 operator sequence

All fourteen full-attempt commands/results above are historical and must
not be replayed. Their authorizations are consumed. No fifteenth run, cleanup,
retry, or deployment is authorized. This operator sequence documents
procedures only; it grants no runtime authority. The T14 read remains
INCONCLUSIVE, Bite 5 remains pending, and production remains unsupported.

1. **Freeze and identify.** Sol records the code revision and hashes of the
   probe, tests, image ID, SDK version, selected CLI version and full binary
   digest. Runtime paths are kept only in the private evidence store. Verify
   the report directory is private and the external observer is ready before
   source launch.
2. **Preflight topology.** Inspect effective settings for the source,
   observer/custodian helpers, and planned target profile. Require network
   disabled, unprivileged read-only roots, dropped capabilities,
   `no-new-privileges`, bounded resources, no host bind, exact engine-managed
   volume destinations, and restart policy `no`. Confirm no source or target
   from another run can be mistaken for this one. Refuse before source launch
   on any mismatch.
3. **Run the source phase.** Start external observation before launching the
   single source container. It contains the source runtime only. Run the
   scripted no-auth scenario with the bounded saved-edit/native-child/tracked
   shell fixtures selected by the frozen harness. Assert that no target
   container or target runtime has been created. Keep all observations on one
   continuous run sequence; do not reset or splice observation epochs.
4. **Stop and custody source.** Use only the frozen harness's bounded source
   stop action. Report natural runtime stop separately from a stop enforced by
   the harness or container engine. Require the source container to be stopped
   and removed before any target creation. Mount its fixture volume
   read-only in the external custodian. Separately inventory `config/` (the
   actual SDK history store) and `workspace/`, record bounded digests and
   byte-prefix facts, and confirm the deterministic saved edit is byte-
   identical. Reject symlinks, hard links, non-regular files, path escapes,
   mutation, or exceeded bounds. Create a distinct target-state volume. A
   copy helper reads source read-only and writes the exact tree, including the
   saved edit, to target. Stop/remove the copier and its writable mount. A
   separate read-only verifier checks the target inventory/digests; stop/remove
   it before release. A read-only pre-release custodian must find exactly one
   JSONL beginning with the source-observed parent history bytes and prove
   that the complete stopped-source transcript is a prefix of the copied
   target transcript. Reconcile the event watcher with the live run-labelled
   container/volume inventory; require every source/helper container
   destroyed, no target, no unresolved create intent, no live writer or
   writable helper mount, and only the source/target state volumes. Bind the
   sanitized history and inventory digests into the release and target-launch
   intents. Any missing or changed item is unresolved; do not release.
5. **Persist explicit release.** The operator selects the explicit-release
   input for the positive arm. Only after source exclusion, custody,
   identity-linked pre-release history custody, exact-copy verification,
   engine inventory reconciliation, effect accounting, and target-spec
   validation pass, atomically persist and fsync a release record bound to source
   invocation, fixture owner/lineage/runner/daemon, source-removal observation
   digest, source manifest digest, pre-release history-custody digest and
   engine-inventory digest, exact target-spec fingerprint, target profile, and
   exact parent UUID. Capture its durable digest and observer
   sequence. The observer must show source removal first, release second, and
   a durable target-launch intent before target creation. An uncertain
   release/intent/effect is never retried. Do not create a target on an
   uncertain release outcome.
6. **Start one target.** After release and the durable launch intent, create
   one separate target container with the verified target-state volume and exact pinned SDK/CLI resume
   path. Require the exact parent UUID from current observed runtime evidence.
   The default `strict-v1` mode keeps the sticky startup-activity gate
   unchanged: a task notification skips its query. Only the separately
   selected, offline-only T049 profile may evaluate one narrow diagnostic
   query after the complete stopped-task startup evidence, pre-`Popen` arrival
   observation, held gateway, exact-parent startup result, and zero-activity
   checks in `contracts/source-only-diagnostic.md` all pass. Any ambiguity,
   extra lifecycle/activity, request, route, partial frame, reader error, or
   missing result refuses the query. That query remains terminal-correlation
   evidence only; it cannot be used to infer replay, quiescence, child
   restoration, or loaded-history capability. Do not retry, launch a duplicate
   target, or send a child restart to improve the result. Verify retained
   source byte prefixes after the bounded startup observation. Mark the
   positive arm OBSERVED only when every selected-mode result and custody
   check passes; the overall diagnostic can say `OBSERVED` only after both the
   positive and negative arms are observed. Bytes retained alone are not proof
   of loaded context.
7. **Stop target, then capture and clean up.** After the bounded startup
   observation, persist target-stop intent before the stop effect. Confirm
   target writer exclusion and record whether shutdown was natural or
   harness-enforced. Only then mount the target-state volume read-only in the
   custodian and verify its bounded tree and retained source byte prefixes.
   Verify all manifests before removing volumes. Preserve sanitized reports
   and private hashes, then clean only the run's containers and volumes.
   Cleanup failure is recorded; it does not justify deleting unverified
   evidence.
8. **Run a separate unknown-effect arm.** Use fresh run IDs and volumes with
   the otherwise-valid explicit-release input selected and one unknown effect
   injected. It must refuse specifically for that effect, persist no release
   authorization, and create no target container. Do not count withholding
   release as this refusal case.

## Stop rules

- A topology, credential, network, volume, restart-policy, observer, or
  validator mismatch refuses before source launch.
- A source observer gap, unexpected source recreation, loss of the source
  process/domain binding, unknown writer/effect, or history custody/copy
  mismatch stops progression before release. Preserve artifacts and launch no
  target.
- A witnessed target creation before durable release, a release
  digest/profile/UUID mismatch, duplicate release, second target launch,
  forbidden file/link shape, changed saved edit, or witnessed wrong parent
  UUID is a known violation and yields Bite 5 FAIL. Do not retry; preserve
  evidence.
- An absent, ambiguous, stale, or unobserved parent UUID, startup activity,
  uncertain request observation, or lost target observer after release is
  INCONCLUSIVE. The default strict gate is never bypassed. Only the separately
  selected T049 diagnostic-only profile may proceed under its exact bounded
  contract; failure of any prerequisite is INCONCLUSIVE and never authorizes a
  retry, duplicate target, or child restart.
- A harness/engine kill is recorded as harness-enforced process termination;
  it is not natural graph shutdown, complete PGID coverage, or production
  containment proof. In the ninth run, source-container shutdown was enforced
  by the harness/engine with exit 137 after the source parent exited and
  tracked fixtures were excluded.
- Do not read or hash target volume contents until the target is stopped and
  writer exclusion is observed. Missing writer-exclusion evidence is
  INCONCLUSIVE, not a successful custody result.
- Any ambiguity after stop may have been dispatched is reported as
  indeterminate. It never authorizes a second stop, target launch, release, or
  production claim.
- On an implementation failure, a one-shot durable-intent stop may contain
  an exact run-labelled live container if no stop intent already exists.
  Preserve stopped containers and every state volume for manual custody review;
  failure cleanup does not force-remove evidence.

## Required evidence outputs

The run record in `live-validation.md` must state the frozen source/test/image
identities; selected SDK/CLI version and full digest; source, helper, and
target isolation results; one continuous observer sequence; source stop and
removal; source history manifest and exact target-copy result; saved-edit
hash/prefix result; durable release binding and ordering; exact-parent result;
startup/request observations; cleanup result; and every unknown or refusal.
Record the selected path and raw IDs only in the private artifact store, not
the report.

Reports and manifests contain no credentials, transcript/request bodies,
history paths, or raw identifiers. Store the private evidence directory with
restricted directory/file modes; record SHA-256 digests for the sanitized
report, source manifest, target-copy manifest, and frozen source/test files.
Every report says `support_claim: false`. Label each observation as runtime,
observer, custodian, or harness-enforced. Do not aggregate Bite 4's result
into a production support claim.

## Bite 5 decision gate

After Sol freezes and publishes the Bite 4 artifacts, Astra reviews their
correlation and limits. The user/root records exactly one verdict:

- **PASS** only if the run satisfies the Bite 3 source evidence contract,
  including the bound source/owner/lineage/runner/daemon identities, complete
  launch-to-exclusion membership and escape coverage, fresh monotonic
  observations joined to a supported OS-domain witness, and a durable
  restart-deny fence enforced by every source creation, recovery, takeover,
  adapter-replacement, and external-supervisor path. PASS also requires the
  source stop, immutable history custody, byte-identical target copy, durable
  release-before-target order, exact-parent target result, complete effect
  accounting, and the privacy/isolation gates above. Fixture ordering, a
  container exit, or successful parent loading alone cannot pass. **Only PASS
  permits public v1 lifecycle implementation.**
- **FAIL** when the run observes a contract violation, such as target creation
  before release, source recreation after its fence, changed history, a
  duplicate target launch, a witnessed wrong parent UUID, unauthorized
  request, forbidden file/link shape, or unsafe writer/effect. Record the
  specific violation; do not retry it away.
- **INCONCLUSIVE** when required evidence is missing, ambiguous, stale,
  truncated, or outside the observed domain. This includes failure to produce
  the Bite 3 OS witness or complete restart-path fence. Retain the fail-closed
  production preflight refusal.

The current source statically lacks the Bite 3 producer, so a fixture-only
observation cannot earn PASS. The verdict must be based on the frozen artifacts
and Astra's written assessment. Astra's T033 architecture review covers only
the future observer correction; it is not the pending Bite 5 evidence
assessment. The second attempt stopped before source runtime; the suspected
mount-builder cause remains unconfirmed. Bite 5 does not
run automatically after Bite 4. No bite authorizes production activation,
installation, deployment, or a live-account canary.
