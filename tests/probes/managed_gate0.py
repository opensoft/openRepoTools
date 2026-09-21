#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Explicit no-auth initialization probe; NEVER certifies native swap support.

Run in the declared Python bench with an existing SDK interpreter and Docker
image. This is deliberately outside pytest discovery. No image is pulled, no
host directory is mounted, and no real profile or SDK user query is used.
The ``positive-orphan`` and ``terminal-cleared`` cases dispatch to the
bounded synthetic-loopback runner, which starts the selected CLI in the same
isolated boundary and requires explicit lifecycle events before reporting an
observed control. The default ``initialization`` case sends a stop request for
a deliberately nonexistent task to test acknowledgement semantics only; it
cannot establish that a real child stopped or durable state cleared. The
optional ``missing-parent-resume`` case resolves a fresh UUID through the
official SDK ``ClaudeAgentOptions(resume=...)`` path and performs only
promptless initialization. It never sends the missing-task stop control.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid


CASES = (
    'initialization', 'missing-parent-resume',
    'positive-orphan', 'terminal-cleared',
)
GATE0_CONTROLS = ('positive_orphan', 'terminal_cleared')
CONTROL_CASES = {
    'positive-orphan': 'positive_orphan',
    'terminal-cleared': 'terminal_cleared',
}
CONTROL_MODES = {
    'positive-orphan': 'positive-orphan',
    'terminal-cleared': 'terminal-cleared',
}
BASELINE_ARGUMENTS = [
    '--output-format', 'stream-json', '--verbose', '--system-prompt', '',
    '--input-format', 'stream-json',
]
UUID4_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
)


def gate0_control_observation(case: str) -> dict[str, object]:
    """Return an explicit preflight refusal for a missing runtime boundary.

    This helper is used before a selected runtime is launched.  The executable
    control path is ``probe(..., case=...)`` below; it invokes the isolated
    loopback runner and replaces this preflight record with its actual,
    event-by-event result.  A caller that only has static fixtures receives a
    refusal rather than a cosmetic ``not-exercised`` claim.
    """
    if case not in GATE0_CONTROLS:
        raise ValueError(f'unsupported Gate 0 control: {case}')
    return {
        'case': case,
        'status': 'unsupported',
        'runtime_attempted': False,
        'selected_runtime_observed': False,
        'observation_surface': 'not-exposed',
        'required_observation': [
            'selected-runtime-lifecycle-events',
            'durable-state-clear-or-orphan-wake',
            'target-no-wake-and-no-model-request',
        ],
        'support_claim': False,
        'reason_codes': [
            'no-supported-public-fixture-boundary',
            'selected-runtime-control-refused-before-mutation',
        ],
    }


def runtime_control_refusal(case: str) -> dict[str, object]:
    """Return the conservative record used when the public arm is absent."""
    return gate0_control_observation(case)


SELECT_RUNTIME = r"""
import hashlib, importlib.metadata, json, sys, uuid
from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport
async def empty():
    if False: yield {}
case = sys.argv[1] if len(sys.argv) > 1 else 'initialization'
if case == 'missing-parent-resume':
    resume_id = str(uuid.uuid4())
    options = ClaudeAgentOptions(resume=resume_id)
else:
    resume_id = None
    options = ClaudeAgentOptions()
transport = SubprocessCLITransport(prompt=empty(), options=options)
selected = transport._find_cli()
transport._cli_path = selected
with open(selected, 'rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
print(json.dumps({'case': case, 'resume_id': resume_id,
                 'sdk_version': importlib.metadata.version('claude-agent-sdk'),
                 'selected_cli': selected, 'cli_sha256': digest,
                 'arguments': transport._build_command()[1:]}))
"""


OBSERVE_INITIALIZE = r"""
import hashlib, json, os, pathlib, selectors, signal, subprocess, sys, time
expected = json.loads(sys.argv[1])
case = expected.get('case', 'initialization')
root = pathlib.Path('/tmp/gate0')
for name in ('home', 'config', 'xdg', 'work'):
    (root / name).mkdir(parents=True, exist_ok=True)
env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(root / 'home'),
       'CLAUDE_CONFIG_DIR': str(root / 'config'), 'XDG_CONFIG_HOME': str(root / 'xdg')}
binary = '/opt/gate0/claude'
with open(binary, 'rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
if digest != expected['cli_sha256']:
    raise RuntimeError('copied selected executable digest mismatch')
version = subprocess.run([binary, '--version'], env=env, capture_output=True,
                         text=True, timeout=15, check=True).stdout.strip()
before_files = set()
for path in root.rglob('*'):
    if path.is_file():
        before_files.add(path.relative_to(root).as_posix())
process = subprocess.Popen([binary, *expected['arguments']], env=env,
    cwd=root / 'work', stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=subprocess.PIPE, start_new_session=True)
output = {process.stdout: bytearray(), process.stderr: bytearray()}
stop_sent = False
stop_send_error = False
initialize_sent = False
initialize_send_error = False
input_offset = 0
missing_task = 'gate0-nonexistent-task'
frames = []
malformed_frames = 0
initialize_success = False
initialize_error = False
initialize_error_classification = None
missing_parent_load_error = False
session_values = []
forced_termination = False
natural_returncode = None

def _mapping(value):
    return value if isinstance(value, dict) else {}

def _text(value):
    if value is None:
        return ''
    if isinstance(value, (list, tuple)):
        return ' '.join(_text(item) for item in value)
    if isinstance(value, dict):
        return ' '.join(_text(item) for item in value.values())
    return str(value)

def _error_classification(event):
    values = []
    for key in ('type', 'subtype', 'error', 'errors', 'message', 'result',
                'reason', 'description'):
        if key in event:
            values.append(_text(event.get(key)))
    response = _mapping(event.get('response'))
    body = _mapping(response.get('response'))
    for item in (response, body):
        for key in ('type', 'subtype', 'error', 'errors', 'message', 'result',
                    'reason', 'description'):
            if key in item:
                values.append(_text(item.get(key)))
    text = ' '.join(values).casefold()
    missing_markers = (
        'no conversation', 'conversation not found', 'session not found',
        'session id not found', 'could not load session', 'failed to load session',
        'load session', 'missing parent', 'parent not found',
    )
    if any(marker in text for marker in missing_markers):
        return 'missing-parent/load'
    if (event.get('is_error') is True or 'error' in text or
            str(event.get('type', '')).casefold() in ('error', 'exception') or
            str(event.get('subtype', '')).casefold().startswith('error')):
        return 'runtime-error'
    return None

def _session_ids(event):
    values = []
    response = _mapping(event.get('response'))
    candidates = [event, response, _mapping(response.get('response')),
                  _mapping(event.get('data')), _mapping(event.get('message'))]
    for item in candidates:
        for key in ('session_id', 'sessionId'):
            value = item.get(key)
            if isinstance(value, str) and value:
                values.append(value)
    return values

def _sanitized_frame(event):
    response = _mapping(event.get('response'))
    body = _mapping(response.get('response'))
    request_id = response.get('request_id') or event.get('request_id')
    if request_id not in ('gate0-init', 'gate0-missing-stop'):
        request_id = 'present' if request_id else None
    subtype = event.get('subtype') or response.get('subtype')
    if not isinstance(subtype, str):
        subtype = None
    body_account = _mapping(body.get('account'))
    error_class = _error_classification(event)
    identities = _session_ids(event)
    return {
        'type': event.get('type') if isinstance(event.get('type'), str) else 'unknown',
        'subtype': subtype,
        'request_id': request_id,
        'token_source': body_account.get('tokenSource') if isinstance(
            body_account.get('tokenSource'), str) else None,
        'probe_task_match': event.get('task_id') == missing_task,
        'task_status': event.get('status') if event.get('task_id') == missing_task
            and isinstance(event.get('status'), str) else None,
        'error_classification': error_class,
        'session_identity_present': bool(identities),
        'session_identity_match': (
            all(value == expected.get('resume_id') for value in identities)
            if identities and expected.get('resume_id') else None),
    }

def _observe_event(event):
    global initialize_success, initialize_error
    global initialize_error_classification, missing_parent_load_error
    if not isinstance(event, dict):
        return
    response = _mapping(event.get('response'))
    request_id = response.get('request_id') or event.get('request_id')
    subtype = event.get('subtype') or response.get('subtype')
    if request_id == 'gate0-init' and subtype == 'success':
        initialize_success = True
    error_class = _error_classification(event)
    if error_class:
        initialize_error = True
        if initialize_error_classification is None:
            initialize_error_classification = error_class
        if error_class == 'missing-parent/load':
            missing_parent_load_error = True
    session_values.extend(_session_ids(event))
    if len(frames) < 128:
        frames.append(_sanitized_frame(event))

def _consume_stdout():
    global input_offset, malformed_frames
    stdout = output[process.stdout]
    while b'\n' in stdout[input_offset:]:
        end = stdout.index(b'\n', input_offset)
        line = stdout[input_offset:end]
        input_offset = end + 1
        try:
            event = json.loads(line)
        except (TypeError, ValueError):
            malformed_frames += 1
            continue
        _observe_event(event)

def _consume_stderr(chunk):
    global missing_parent_load_error, initialize_error, initialize_error_classification
    text = chunk.decode(errors='replace').casefold()
    if any(marker in text for marker in (
            'no conversation', 'conversation not found', 'session not found',
            'session id not found', 'could not load session',
            'failed to load session', 'load session', 'missing parent',
            'parent not found')):
        missing_parent_load_error = True
        initialize_error = True
        if initialize_error_classification is None:
            initialize_error_classification = 'missing-parent/load'

def _drain_once(timeout):
    for key, _ in selector.select(timeout):
        chunk = os.read(key.fileobj.fileno(), 65536)
        if chunk:
            output[key.fileobj].extend(chunk)
            if key.fileobj is process.stdout:
                _consume_stdout()
            else:
                _consume_stderr(chunk)
        else:
            selector.unregister(key.fileobj)

selector = selectors.DefaultSelector()
try:
    selector.register(process.stdout, selectors.EVENT_READ)
    selector.register(process.stderr, selectors.EVENT_READ)
    try:
        process.stdin.write(b'{"type":"control_request","request_id":"gate0-init",'
                            b'"request":{"subtype":"initialize"}}\n')
        process.stdin.flush()
        initialize_sent = True
    except (BrokenPipeError, OSError):
        initialize_send_error = True
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline and selector.get_map():
        _drain_once(.2)
        if sum(map(len, output.values())) > 1048576:
            raise RuntimeError('probe output exceeds bounded capture')
        # Only the baseline case exercises the documented stop_task control.
        # The negative resume case intentionally remains promptless and sends
        # no task control, even when initialization succeeds.
        if (case == 'initialization' and not stop_sent and initialize_success):
            if process.poll() is not None or process.stdin.closed:
                break
            try:
                process.stdin.write((json.dumps({'type': 'control_request',
                    'request_id': 'gate0-missing-stop', 'request': {
                    'subtype': 'stop_task', 'task_id': missing_task}}) + '\n').encode())
                process.stdin.flush()
                stop_sent = True
            except (BrokenPipeError, OSError):
                stop_send_error = True
        if process.poll() is not None:
            break
    # A natural exit can leave a final stdout/stderr tail ready to read. Drain
    # it before recording the exit and before any forced cleanup signal.
    drain_deadline = min(time.monotonic() + .5, deadline)
    while selector.get_map() and time.monotonic() < drain_deadline:
        _drain_once(.05)
    natural_returncode = process.poll()
finally:
    # Preserve the natural exit observation separately from cleanup. A process
    # still alive at the bound is forcibly terminated and is never reported as
    # a runtime loader result.
    if natural_returncode is None:
        natural_returncode = process.poll()
    if process.poll() is None:
        forced_termination = True
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        forced_termination = True
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)
after_files = set()
for path in root.rglob('*'):
    if path.is_file():
        after_files.add(path.relative_to(root).as_posix())
stderr_text = output[process.stderr].decode(errors='replace').casefold()
if any(marker in stderr_text for marker in (
        'no conversation', 'conversation not found', 'session not found',
        'session id not found', 'could not load session',
        'failed to load session', 'load session', 'missing parent',
        'parent not found')):
    missing_parent_load_error = True
    initialize_error = True
    if initialize_error_classification is None:
        initialize_error_classification = 'missing-parent/load'
transcript_files = [path for path in after_files - before_files
                    if path.casefold().endswith('.jsonl') and
                    ('project' in path.casefold() or 'transcript' in path.casefold())]
session_present = bool(session_values)
session_match = (all(value == expected.get('resume_id') for value in session_values)
                 if session_values and expected.get('resume_id') else None)
print(json.dumps({'case': case, 'cli_version': version, 'cli_sha256': digest,
    'frames': frames, 'malformed_frame_count': malformed_frames,
    'initialization': {
        'success': initialize_success,
        'error': initialize_error,
        'error_classification': initialize_error_classification,
        'missing_parent_load_error': missing_parent_load_error,
        'session_identity_present': session_present,
        'session_identity_match': session_match,
    },
    'missing_parent_load_error': missing_parent_load_error,
    'missing_task_stop_sent': stop_sent,
    'initialize_request_sent': initialize_sent,
    'initialize_send_error': initialize_send_error,
    'stop_send_error': stop_send_error,
    'user_frames_sent': 0,
    'child_returncode': process.returncode, 'child_reaped': True,
    'natural_exit': natural_returncode is not None,
    'natural_returncode': natural_returncode,
    'forced_termination': forced_termination,
    'native_transcript_write_detected': bool(transcript_files),
    'native_transcript_file_count': len(transcript_files),
    'positive_orphan': {
        'status': 'unsupported',
        'reason_codes': ['selected-runtime-control-not-selected'],
        'support_claim': False,
    },
    'terminal_cleared': {
        'status': 'unsupported',
        'reason_codes': ['selected-runtime-control-not-selected'],
        'support_claim': False,
    },
    'model_dispatch': 'unknown', 'load_proven': False,
    'exact_resume_claim': False, 'verdict': 'inconclusive', 'support_claim': False,
    'reason_codes': ['orphan-positive-control-not-selected', 'terminal-stop-not-selected',
                     'model-dispatch-unknown']}))
"""


def missing_task_observation(observed: dict) -> dict:
    """A successful control response is never terminal child evidence."""
    frames = observed.get('frames', [])
    if not isinstance(frames, (list, tuple)):
        frames = []
    responses = [frame for frame in frames if isinstance(frame, dict)
                 and frame.get('type') == 'control_response'
                 and frame.get('request_id') == 'gate0-missing-stop']
    response = responses[0].get('subtype') if len(responses) == 1 else 'unknown'
    if response not in ('success', 'error'):
        response = 'unknown'
    notifications = [frame for frame in frames if isinstance(frame, dict)
                     and frame.get('type') == 'system'
                     and frame.get('subtype') == 'task_notification'
                     and frame.get('probe_task_match') is True]
    return {'request_sent': observed.get('missing_task_stop_sent') is True,
            'control_response': response,
            'matching_terminal_notifications': sum(
                isinstance(frame.get('task_status'), str) and
                frame.get('task_status') in ('stopped', 'completed', 'failed')
                for frame in notifications),
            'real_child_stop_proven': False, 'durable_clear_proven': False}


def validate_selected_runtime(selected: dict, case: str) -> None:
    """Require the exact SDK-derived launch shape for one isolated case."""
    if case not in CASES or selected.get('case') != case:
        raise RuntimeError('selected runtime case does not match requested probe case')
    arguments = selected.get('arguments')
    if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
        raise RuntimeError('SDK launch arguments are malformed')
    resume_id = selected.get('resume_id')
    if case == 'initialization' or case in CONTROL_CASES:
        if arguments != BASELINE_ARGUMENTS or resume_id is not None:
            raise RuntimeError('SDK launch arguments changed; review the probe')
        return
    if not isinstance(resume_id, str) or not UUID4_RE.fullmatch(resume_id):
        raise RuntimeError('missing-parent case did not use a fresh UUIDv4')
    expected = BASELINE_ARGUMENTS[:5] + [f'--resume={resume_id}'] + BASELINE_ARGUMENTS[5:]
    if arguments != expected:
        raise RuntimeError('SDK resume launch arguments changed; review the probe')


def missing_parent_resume_observation(observed: dict) -> dict:
    """Summarize the negative resume case without claiming exact loading."""
    initialization = observed.get('initialization')
    if not isinstance(initialization, dict):
        initialization = {}
    return {
        'case': 'missing-parent-resume',
        'missing_task_stop_sent': observed.get('missing_task_stop_sent') is True,
        'stop_control_forbidden': observed.get('missing_task_stop_sent') is not True,
        'init_success': initialization.get('success') is True,
        'init_error': initialization.get('error') is True,
        'missing_parent_load_error': initialization.get(
            'missing_parent_load_error') is True,
        'session_identity_present': initialization.get(
            'session_identity_present') is True,
        'session_identity_match': initialization.get('session_identity_match'),
        'model_dispatch': 'unknown',
        'load_proven': False,
        'exact_resume_claim': False,
        'support_claim': False,
    }


def run(*command: str, **kwargs) -> subprocess.CompletedProcess:
    timeout = kwargs.pop('timeout', 45)
    return subprocess.run(command, check=True, capture_output=True,
                          timeout=timeout, **kwargs)


def validate_isolation(record: dict) -> None:
    config = record['HostConfig']
    if (config['NetworkMode'] != 'none' or record.get('Mounts') or
            not config['ReadonlyRootfs'] or config['Privileged'] or
            config.get('PidMode') or config.get('CapAdd') or
            config.get('Devices') or config.get('DeviceRequests') or
            config.get('CapDrop') != ['ALL'] or
            'no-new-privileges' not in config.get('SecurityOpt', [])):
        raise RuntimeError('disposable probe isolation was not established')


def _selected_runtime_matches(
    selected: dict[str, object],
    observation: dict[str, object],
) -> bool:
    runtime = observation.get('runtime')
    if not isinstance(runtime, dict):
        return False
    return (
        runtime.get('sdk_version') == selected.get('sdk_version')
        and runtime.get('selected_cli_path') == selected.get('selected_cli')
        and runtime.get('selected_cli_sha256') == selected.get('cli_sha256')
    )


def run_selected_control(
    sdk_python: str,
    image: str,
    case: str,
    selected: dict[str, object],
) -> dict[str, object]:
    """Execute one bounded control through the isolated loopback runner.

    The loopback runner owns the disposable network-none container and the
    selected CLI startup.  This wrapper only checks runtime identity and
    projects the runner's independently assessed control result; it never
    creates lifecycle events or promotes the checked-in fixtures.
    """
    if case not in CONTROL_CASES:
        raise ValueError(f'unsupported selected-runtime control case: {case}')
    control_script = Path(__file__).with_name('managed_native_loopback.py')
    with tempfile.TemporaryDirectory(prefix='managed-gate0-control-') as tmp:
        report_path = Path(tmp) / 'loopback.json'
        run(
            sdk_python,
            str(control_script),
            '--sdk-python', sdk_python,
            '--image', image,
            '--control-mode', CONTROL_MODES[case],
            '--output', str(report_path),
            timeout=150,
        )
        with report_path.open(encoding='utf-8') as report:
            loopback = json.load(report)
    if not isinstance(loopback, dict):
        raise RuntimeError('selected-runtime control report is malformed')
    runtime_observed = _selected_runtime_matches(selected, loopback)
    control_key = CONTROL_CASES[case]
    control = loopback.get(control_key)
    if not isinstance(control, dict):
        control = runtime_control_refusal(case)
        control['runtime_attempted'] = bool(loopback.get('runtime'))
        control['selected_runtime_observed'] = runtime_observed
        control['observation_surface'] = (
            'selected-runtime-loopback-missing-control-record'
        )
        control['reason_codes'] = sorted(set(
            list(control['reason_codes'])
            + ['selected-runtime-control-record-missing']
        ))
    else:
        control = dict(control)
        control['case'] = case
        control['runtime_attempted'] = bool(loopback.get('runtime'))
        control['selected_runtime_observed'] = runtime_observed
        control['support_claim'] = False
        if not runtime_observed:
            control['status'] = 'unsupported'
            control['reason_codes'] = sorted(set(
                list(control.get('reason_codes', []))
                + ['selected-runtime-identity-mismatch']
            ))
    controls = {
        name: runtime_control_refusal(name)
        for name in GATE0_CONTROLS
    }
    controls[control_key] = control
    return {
        'schema': 'managed-gate0/v2',
        'case': case,
        'selected_runtime': selected,
        'selected_runtime_observation': loopback,
        'gate0_controls': controls,
        'control': control,
        'network': 'none',
        'auth': 'synthetic-loopback-dummy-key-only',
        'support_claim': False,
        'verdict': 'inconclusive',
        'sandbox_removed': loopback.get('sandbox_removed') is True,
        'reason_codes': sorted(set(
            list(loopback.get('reason_codes', []))
            + list(control.get('reason_codes', []))
        )),
    }


def probe(sdk_python: str, image: str, case: str = 'initialization') -> dict:
    if case not in CASES:
        raise ValueError(f'unsupported probe case: {case}')
    # Isolate even the read-only SDK selector from the user's configuration.
    with tempfile.TemporaryDirectory(prefix='managed-gate0-select-') as tmp:
        selected = json.loads(run(sdk_python, '-I', '-c', SELECT_RUNTIME, case,
            env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': tmp,
                 'CLAUDE_CONFIG_DIR': tmp}).stdout)
    validate_selected_runtime(selected, case)
    if case in CONTROL_CASES:
        return run_selected_control(sdk_python, image, case, selected)
    image_id = json.loads(run('docker', 'image', 'inspect', image).stdout)[0]['Id']
    name = 'managed-gate0-' + uuid.uuid4().hex[:12]
    container = run('docker', 'create', '--name', name, '--network', 'none',
        '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
        '--pids-limit', '96', '--memory', '768m', '--cpus', '1',
        '--tmpfs', '/tmp:rw,nosuid,nodev,size=96m',
        '--tmpfs', '/opt/gate0:rw,exec,nosuid,nodev,size=256m',
        '--entrypoint', '/bin/sleep', image_id, '180').stdout.decode().strip()
    try:
        record = json.loads(run('docker', 'inspect', container).stdout)[0]
        validate_isolation(record)
        run('docker', 'start', container)
        with open(selected['selected_cli'], 'rb') as executable:
            run('docker', 'exec', '-i', container, 'sh', '-c',
                'cat > /opt/gate0/claude && chmod 500 /opt/gate0/claude',
                stdin=executable)
        record = json.loads(run('docker', 'inspect', container).stdout)[0]
        validate_isolation(record)
        observed = json.loads(run('docker', 'exec', '-i', container,
            '/usr/bin/env', '-i', 'PATH=/usr/local/bin:/usr/bin:/bin', 'python3',
            '-', json.dumps(selected), input=OBSERVE_INITIALIZE.encode()).stdout)
        observed.update({'selected_runtime': selected, 'image_id': image_id,
                         'network': 'none', 'auth': 'none', 'host_mounts': [],
                         'case': case})
        observed['gate0_controls'] = {
            control: gate0_control_observation(control)
            for control in GATE0_CONTROLS
        }
        if case == 'initialization':
            observed['missing_task_control'] = missing_task_observation(observed)
        else:
            observed['missing_parent_resume_control'] = missing_parent_resume_observation(
                observed)
    finally:
        # Target only the exact container this invocation created. Cleanup
        # failure is an error, never a successful inconclusive observation.
        run('docker', 'rm', '-f', container)
    observed['sandbox_removed'] = True
    return observed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-python', required=True)
    parser.add_argument('--image', required=True, help='existing local bench image')
    parser.add_argument('--case', choices=CASES, default='initialization',
                        help='bounded control to run (default: initialization)')
    parser.add_argument('--output', type=Path, required=True,
                        help='new private observation file; never a capability grant')
    args = parser.parse_args()
    # Reserve the report before any runtime action; never overwrite evidence.
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as report:
        try:
            observed = probe(args.sdk_python, args.image, args.case)
        except Exception:
            report.write(json.dumps({'case': args.case, 'verdict': 'inconclusive',
                'support_claim': False, 'reason_codes': ['probe-failed'],
                'gate0_controls': {
                    control: gate0_control_observation(control)
                    for control in GATE0_CONTROLS
                },
                'cleanup_verified': False}) + '\n')
            raise
        json.dump(observed, report, indent=2)
        report.write('\n')
    print(f'INCONCLUSIVE: {args.case} control only; native swap remains unverified')


if __name__ == '__main__':
    main()
