#!/bin/bash
set -euo pipefail
umask 077
ulimit -f 512
: "${PROBE_METADATA_PARENT:?}"
: "${PROBE_METADATA_ID:?}"
: "${PROBE_SOURCE_VOLUME:?}"
: "${PROBE_SOURCE_RUN_ID:?}"
: "${PROBE_IMAGE:?}"
: "${PROBE_METADATA_RUNNER:?}"
: "${PROBE_METADATA_RUNNER_SHA256:?}"
: "${PROBE_METADATA_RUNNER_CALLER_STAT:?}"
: "${PROBE_METADATA_PARENT_CALLER_STAT:?}"
test "$PROBE_IMAGE" = "sha256:a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094"
case "$PROBE_METADATA_ID" in ''|*[!0-9a-f]*) exit 2 ;; esac
test "${#PROBE_METADATA_ID}" = 32
case "$PROBE_METADATA_PARENT" in /*) ;; *) exit 2 ;; esac
test "$0" = "$PROBE_METADATA_RUNNER"
test "${BASH_SOURCE[0]}" = "$PROBE_METADATA_RUNNER"
test "$(realpath -e -- "$PROBE_METADATA_RUNNER")" = "$PROBE_METADATA_RUNNER"
test -f "$PROBE_METADATA_RUNNER" && test ! -L "$PROBE_METADATA_RUNNER"
test "$(stat -c %a "$PROBE_METADATA_RUNNER")" = 644
RUNNER_CONTAINER_STAT="$(stat -c '%d:%i:%u:%g:%a:%s' "$PROBE_METADATA_RUNNER")"
test "$RUNNER_CONTAINER_STAT" = "$PROBE_METADATA_RUNNER_CALLER_STAT"
RUNNER_PYBENCH_SHA256="$(sha256sum "$PROBE_METADATA_RUNNER" | cut -d ' ' -f1)"
test "$RUNNER_PYBENCH_SHA256" = "$PROBE_METADATA_RUNNER_SHA256"
case "$PROBE_METADATA_RUNNER_SHA256" in ''|*[!0-9a-f]*) exit 2 ;; esac
test "${#PROBE_METADATA_RUNNER_SHA256}" = 64
test -d "$PROBE_METADATA_PARENT" && test ! -L "$PROBE_METADATA_PARENT"
test "$(realpath -e -- "$PROBE_METADATA_PARENT")" = "$PROBE_METADATA_PARENT"
test "$(stat -c %a "$PROBE_METADATA_PARENT")" = 700
test "$(stat -c '%d:%i:%u:%g:%a' "$PROBE_METADATA_PARENT")" = "$PROBE_METADATA_PARENT_CALLER_STAT"
test -w "$PROBE_METADATA_PARENT"
META_DIR="$PROBE_METADATA_PARENT/metadata"
test -n "$META_DIR"
test "$META_DIR" = "$PROBE_METADATA_PARENT/metadata"
case "$META_DIR" in /*) ;; *) exit 2 ;; esac
test ! -e "$META_DIR" && test ! -L "$META_DIR"
mkdir "$META_DIR"
chmod 700 "$META_DIR"
test -d "$META_DIR" && test ! -L "$META_DIR"
test "$(stat -c %a "$META_DIR")" = 700
test -w "$META_DIR"
META_SENTINEL="$META_DIR/prefix.sentinel"
test ! -e "$META_SENTINEL" && test ! -L "$META_SENTINEL"
META_SENTINEL_VALUE="openrepotools-bite4-metadata-prefix-v1|$PROBE_METADATA_PARENT|$META_DIR|$PROBE_METADATA_ID|$RUNNER_PYBENCH_SHA256"
printf '%s\n' "$META_SENTINEL_VALUE" > "$META_SENTINEL"
chmod 600 "$META_SENTINEL"
test -f "$META_SENTINEL" && test ! -L "$META_SENTINEL"
test "$(stat -c %a "$META_SENTINEL")" = 600
test "$(cat "$META_SENTINEL")" = "$META_SENTINEL_VALUE"
META_CONTAINER="openrepotools-bite4-meta-$PROBE_METADATA_ID"
case "$PROBE_METADATA_ID" in ''|*[!0-9a-f]*) exit 2 ;; esac
test "${#PROBE_METADATA_ID}" = 32
test "$(docker image inspect --format '{{.Id}}' "$PROBE_IMAGE")" = \
  "sha256:a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094"
test "$(sha256sum tests/probes/inspect_two_domain_volume_metadata.py | cut -d ' ' -f1)" = \
  "fbff3be87a288501d64d977e91d37ba01f5bb43ad596e211e1ca691ea9f81c39"
SCAN_SOURCE="$(cat tests/probes/inspect_two_domain_volume_metadata.py)"
EMBEDDED_SHA256="$(printf %s "$SCAN_SOURCE" | sha256sum | cut -d ' ' -f1)"
test "$EMBEDDED_SHA256" = \
  "abbe57cc78fdfe4b613df7c421af8447b10fa00bd4edd4ff0c21c4f3029dc683"

docker volume inspect "$PROBE_SOURCE_VOLUME" \
  > "$META_DIR/source-volume.inspect.json" 2> "$META_DIR/source-volume.inspect.stderr"
python3 -I -S - "$META_DIR/source-volume.inspect.json" "$PROBE_SOURCE_VOLUME" "$PROBE_SOURCE_RUN_ID" <<'PY'
import json, sys
with open(sys.argv[1], "rb") as stream:
    records = json.load(stream)
assert isinstance(records, list) and len(records) == 1
record = records[0]
assert record.get("Name") == sys.argv[2]
assert record.get("Driver") == "local" and record.get("Scope") == "local"
assert record.get("Options") in (None, {})
assert record.get("Labels") == {
    "openrepotools.bite4.run": sys.argv[3],
    "openrepotools.bite4.role": "source-state",
}
PY
set +e
( ulimit -f 128
  /usr/bin/timeout --signal=TERM --kill-after=5s 10s \
    docker ps --quiet --filter "volume=$PROBE_SOURCE_VOLUME" \
      > "$META_DIR/pre-existing-running.stdout" \
      2> "$META_DIR/pre-existing-running.stderr"
)
PREEXISTING_PS_STATUS=$?
set -e
test "$PREEXISTING_PS_STATUS" -eq 0
test ! -s "$META_DIR/pre-existing-running.stdout"

# Recheck the private prefix and static-source binding immediately before the
# first Docker create; any mismatch stops before the effect.
test -f "$PROBE_METADATA_RUNNER" && test ! -L "$PROBE_METADATA_RUNNER"
test "$(stat -c %a "$PROBE_METADATA_RUNNER")" = 644
test "$(stat -c '%d:%i:%u:%g:%a:%s' "$PROBE_METADATA_RUNNER")" = "$PROBE_METADATA_RUNNER_CALLER_STAT"
test "$(sha256sum "$PROBE_METADATA_RUNNER" | cut -d ' ' -f1)" = "$PROBE_METADATA_RUNNER_SHA256"
test -f "$META_SENTINEL" && test ! -L "$META_SENTINEL"
test "$(stat -c %a "$META_SENTINEL")" = 600
test "$(cat "$META_SENTINEL")" = "$META_SENTINEL_VALUE"

docker create --pull never \
  --name "$META_CONTAINER" \
  --label "openrepotools.bite4.meta.id=$PROBE_METADATA_ID" \
  --label "openrepotools.bite4.meta.role=readonly-volume-metadata" \
  --label "openrepotools.bite4.meta.source-run=$PROBE_SOURCE_RUN_ID" \
  --network none --ipc none --read-only --cap-drop ALL \
  --security-opt no-new-privileges=true \
  --pids-limit 8 --memory 128m --memory-swap 128m --cpus 0.50 \
  --ulimit nofile=1024:1024 \
  --restart=no --no-healthcheck --log-driver none --stop-timeout 5 \
  --user 0:0 \
  --mount "type=volume,src=$PROBE_SOURCE_VOLUME,dst=/evidence,readonly,volume-nocopy" \
  --entrypoint /usr/bin/env "$PROBE_IMAGE" -i PATH=/usr/local/bin:/usr/bin:/bin \
  python3 -I -S -B -u -c "$SCAN_SOURCE" \
  > "$META_DIR/create.stdout" 2> "$META_DIR/create.stderr"
META_CONTAINER_ID="$(cat "$META_DIR/create.stdout")"
python3 -I -S - "$META_CONTAINER_ID" <<'PY'
import re, sys
assert re.fullmatch(r"[0-9a-f]{64}", sys.argv[1])
PY
docker inspect "$META_CONTAINER_ID" \
  > "$META_DIR/pre-start.inspect.json" 2> "$META_DIR/pre-start.inspect.stderr"
python3 -I -S - "$META_DIR/pre-start.inspect.json" "$META_CONTAINER_ID" \
  "$PROBE_METADATA_ID" "$PROBE_SOURCE_RUN_ID" "$PROBE_SOURCE_VOLUME" \
  "$EMBEDDED_SHA256" <<'PY'
import hashlib, json, sys
with open(sys.argv[1], "rb") as stream:
    rows = json.load(stream)
assert isinstance(rows, list) and len(rows) == 1
r = rows[0]
config, host, state = r["Config"], r["HostConfig"], r["State"]
labels = config["Labels"]
assert r["Id"] == sys.argv[2] and r["Image"] == "sha256:a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094"
assert labels.get("openrepotools.bite4.meta.id") == sys.argv[3]
assert labels.get("openrepotools.bite4.meta.role") == "readonly-volume-metadata"
assert labels.get("openrepotools.bite4.meta.source-run") == sys.argv[4]
assert config["Entrypoint"] == ["/usr/bin/env"]
cmd = config["Cmd"]
assert cmd[:8] == ["-i", "PATH=/usr/local/bin:/usr/bin:/bin", "python3", "-I", "-S", "-B", "-u", "-c"]
assert len(cmd) == 9 and hashlib.sha256(cmd[8].encode("utf-8")).hexdigest() == sys.argv[6]
health = config.get("Healthcheck")
assert config.get("User") == "0:0"
assert health is None or (isinstance(health, dict) and health.get("Test") == ["NONE"])
assert config.get("OpenStdin") is False and config.get("AttachStdin") is False and config.get("Tty") is False
assert state.get("Status") == "created" and state.get("Running") is False
assert host.get("NetworkMode") == "none" and host.get("IpcMode") == "none"
assert host.get("ReadonlyRootfs") is True and host.get("Privileged") is False
assert host.get("CapDrop") == ["ALL"] and not host.get("CapAdd")
assert "no-new-privileges=true" in (host.get("SecurityOpt") or [])
assert host.get("PidsLimit") == 8 and host.get("Memory") == 134217728
assert host.get("MemorySwap") == 134217728 and host.get("NanoCpus") == 500000000
assert host.get("RestartPolicy", {}).get("Name") == "no"
assert host.get("LogConfig", {}).get("Type") == "none"
assert host.get("AutoRemove") is False and not host.get("Binds") and not host.get("VolumesFrom")
assert not host.get("Devices") and not host.get("Tmpfs")
mounts = host.get("Mounts") or []
assert len(mounts) == 1
m = mounts[0]
assert m.get("Type") == "volume" and m.get("Source") == sys.argv[5]
assert m.get("Target") == "/evidence" and m.get("ReadOnly") is True
assert m.get("VolumeOptions", {}).get("NoCopy") is True
actual = r.get("Mounts") or []
assert len(actual) == 1
assert actual[0].get("Type") == "volume" and actual[0].get("Name") == sys.argv[5]
assert actual[0].get("Destination") == "/evidence" and actual[0].get("RW") is False
PY

set +e
( ulimit -f 128
  /usr/bin/timeout --signal=TERM --kill-after=5s 20s \
    docker start -a "$META_CONTAINER_ID" \
      > "$META_DIR/metadata.private.json" 2> "$META_DIR/start.stderr"
)
ATTACH_STATUS=$?
set -e
printf '%s\n' "$ATTACH_STATUS" > "$META_DIR/attach.exit"
set +e
/usr/bin/timeout --signal=TERM --kill-after=5s 10s docker inspect "$META_CONTAINER_ID" \
  > "$META_DIR/after-start.inspect.json" 2> "$META_DIR/after-start.inspect.stderr"
INSPECT_STATUS=$?
set -e
if [ "$INSPECT_STATUS" -ne 0 ]; then
  set +e
  /usr/bin/timeout --signal=TERM --kill-after=5s 10s \
    docker stop --time 5 "$META_CONTAINER_ID" \
      > "$META_DIR/stop.stdout" 2> "$META_DIR/stop.stderr"
  /usr/bin/timeout --signal=TERM --kill-after=5s 10s docker inspect "$META_CONTAINER_ID" \
    > "$META_DIR/post-stop.inspect.json" 2> "$META_DIR/post-stop.inspect.stderr"
  set -e
  exit 2
fi
STATE_FACTS="$(python3 -I -S - "$META_DIR/after-start.inspect.json" <<'PY'
import json, sys
try:
    with open(sys.argv[1], "rb") as stream:
        rows = json.load(stream)
    assert isinstance(rows, list) and len(rows) == 1
    state = rows[0]["State"]
    running = state["Running"]
    assert isinstance(running, bool)
    print("%s\t%s\t%s" % (state["Status"], state["ExitCode"], "true" if running else "false"))
except Exception:
    print("unknown\tunknown\tunknown")
PY
)"
STATE_NAME="$(printf '%s' "$STATE_FACTS" | cut -f1)"
STATE_EXIT="$(printf '%s' "$STATE_FACTS" | cut -f2)"
RUNNING="$(printf '%s' "$STATE_FACTS" | cut -f3)"
if [ "$RUNNING" != false ]; then
  set +e
  /usr/bin/timeout --signal=TERM --kill-after=5s 10s \
    docker stop --time 5 "$META_CONTAINER_ID" \
      > "$META_DIR/stop.stdout" 2> "$META_DIR/stop.stderr"
  /usr/bin/timeout --signal=TERM --kill-after=5s 10s docker inspect "$META_CONTAINER_ID" \
    > "$META_DIR/post-stop.inspect.json" 2> "$META_DIR/post-stop.inspect.stderr"
  set -e
  exit 2
fi
if [ "$STATE_NAME" != exited ] || { [ "$ATTACH_STATUS" -ne 0 ] && [ "$ATTACH_STATUS" -ne 2 ]; } \
    || { [ "$ATTACH_STATUS" -eq 0 ] && [ "$STATE_EXIT" -ne 0 ]; } \
    || { [ "$ATTACH_STATUS" -eq 2 ] && [ "$STATE_EXIT" -ne 2 ]; }; then
  exit 2
fi
python3 -I -S - "$META_DIR/after-start.inspect.json" "$META_CONTAINER_ID" \
  "$PROBE_METADATA_ID" "$PROBE_SOURCE_RUN_ID" "$PROBE_SOURCE_VOLUME" \
  "$EMBEDDED_SHA256" "$STATE_EXIT" <<'PY'
import hashlib, json, sys
with open(sys.argv[1], "rb") as stream:
    rows = json.load(stream)
assert isinstance(rows, list) and len(rows) == 1
r = rows[0]
config, state = r["Config"], r["State"]
labels = config["Labels"]
assert r["Id"] == sys.argv[2]
assert r["Image"] == "sha256:a26ded22be5a5f7e187b6e59d926dc49108b668d1e5a6227681025ecb09c7094"
assert labels.get("openrepotools.bite4.meta.id") == sys.argv[3]
assert labels.get("openrepotools.bite4.meta.role") == "readonly-volume-metadata"
assert labels.get("openrepotools.bite4.meta.source-run") == sys.argv[4]
assert hashlib.sha256(config["Cmd"][8].encode("utf-8")).hexdigest() == sys.argv[6]
assert state.get("Status") == "exited" and state.get("Running") is False
assert str(state.get("ExitCode")) == sys.argv[7]
mounts = r.get("Mounts") or []
assert len(mounts) == 1
m = mounts[0]
assert m.get("Type") == "volume" and m.get("Name") == sys.argv[5]
assert m.get("Destination") == "/evidence" and m.get("RW") is False
PY
set +e
/usr/bin/timeout --signal=TERM --kill-after=5s 10s \
  docker volume inspect "$PROBE_SOURCE_VOLUME" \
    > "$META_DIR/post-volume.inspect.json" 2> "$META_DIR/post-volume.inspect.stderr"
POST_VOLUME_STATUS=$?
set -e
test "$POST_VOLUME_STATUS" -eq 0
python3 -I -S - "$META_DIR/post-volume.inspect.json" "$PROBE_SOURCE_VOLUME" \
  "$PROBE_SOURCE_RUN_ID" <<'PY'
import json, sys
with open(sys.argv[1], "rb") as stream:
    rows = json.load(stream)
assert isinstance(rows, list) and len(rows) == 1
volume = rows[0]
assert volume.get("Name") == sys.argv[2]
assert volume.get("Driver") == "local" and volume.get("Scope") == "local"
assert volume.get("Options") in (None, {})
assert volume.get("Labels") == {
    "openrepotools.bite4.run": sys.argv[3],
    "openrepotools.bite4.role": "source-state",
}
PY
set +e
( ulimit -f 128
  /usr/bin/timeout --signal=TERM --kill-after=5s 10s \
    docker ps --quiet --filter "volume=$PROBE_SOURCE_VOLUME" \
      > "$META_DIR/postscan-running.stdout" \
      2> "$META_DIR/postscan-running.stderr"
)
POSTSCAN_PS_STATUS=$?
set -e
test "$POSTSCAN_PS_STATUS" -eq 0
test ! -s "$META_DIR/postscan-running.stdout"
test "$(stat -c %s "$META_DIR/metadata.private.json")" -le 65536
test "$(stat -c %s "$META_DIR/start.stderr")" -le 131072
test "$(stat -c %a "$META_DIR/metadata.private.json")" = 600
set +e
python3 -I -S tests/probes/inspect_two_domain_volume_metadata.py \
  --public-from "$META_DIR/metadata.private.json" \
  > "$META_DIR/metadata.public.json" 2> "$META_DIR/public.stderr"
PROJECTION_STATUS=$?
set -e
if [ "$ATTACH_STATUS" -eq 0 ] && [ "$STATE_EXIT" -eq 0 ]; then
  test "$PROJECTION_STATUS" -eq 0
else
  test "$PROJECTION_STATUS" -eq 2
fi
chmod 600 "$META_DIR/metadata.public.json" "$META_DIR/public.stderr"
