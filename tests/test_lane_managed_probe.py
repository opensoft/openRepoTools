# SPDX-License-Identifier: Apache-2.0
"""Probe isolation checks; no Docker, SDK, network or credentials are used."""

import copy
from pathlib import Path
import runpy

import pytest


PROBE = runpy.run_path(str(Path(__file__).parent / 'probes' / 'managed_gate0.py'))


def isolated_container():
    return {'Mounts': [], 'HostConfig': {
        'NetworkMode': 'none', 'ReadonlyRootfs': True, 'Privileged': False,
        'PidMode': '', 'CapAdd': [], 'CapDrop': ['ALL'], 'Devices': [],
        'DeviceRequests': [], 'SecurityOpt': ['no-new-privileges'],
    }}


def test_gate0_probe_accepts_literal_isolated_container_only():
    PROBE['validate_isolation'](isolated_container())


@pytest.mark.parametrize(('key', 'value'), [
    ('NetworkMode', 'container:another-container'),
    ('NetworkMode', 'host'),
    ('NetworkMode', 'default'),
    ('ReadonlyRootfs', False),
    ('Privileged', True),
    ('PidMode', 'host'),
    ('CapAdd', ['SYS_ADMIN']),
    ('CapDrop', []),
    ('Devices', [{'PathOnHost': '/dev/example'}]),
    ('DeviceRequests', [{'Count': -1}]),
    ('SecurityOpt', []),
])
def test_gate0_probe_refuses_weakened_isolation(key, value):
    record = isolated_container()
    record['HostConfig'][key] = value
    with pytest.raises(RuntimeError, match='isolation'):
        PROBE['validate_isolation'](record)


def test_gate0_probe_refuses_host_mount_even_with_no_network():
    record = copy.deepcopy(isolated_container())
    record['Mounts'] = [{'Type': 'bind', 'Source': '/private', 'Destination': '/data'}]
    with pytest.raises(RuntimeError, match='isolation'):
        PROBE['validate_isolation'](record)


@pytest.mark.parametrize('subtype', ['success', 'error'])
def test_missing_task_acknowledgement_never_proves_real_child_stop(subtype):
    result = PROBE['missing_task_observation']({
        'missing_task_stop_sent': True,
        'frames': [{'type': 'control_response', 'request_id': 'gate0-missing-stop',
                    'subtype': subtype}],
    })
    assert result == {'request_sent': True, 'control_response': subtype,
                      'matching_terminal_notifications': 0,
                      'real_child_stop_proven': False, 'durable_clear_proven': False}


def test_missing_task_duplicate_responses_are_unknown_and_unrelated_events_do_not_join():
    response = {'type': 'control_response', 'request_id': 'gate0-missing-stop',
                'subtype': 'success'}
    result = PROBE['missing_task_observation']({
        'missing_task_stop_sent': True,
        'frames': [response, response,
                   {'type': 'system', 'subtype': 'task_notification',
                    'probe_task_match': False, 'task_status': 'stopped'}],
    })
    assert result['control_response'] == 'unknown'
    assert result['matching_terminal_notifications'] == 0
    assert result['real_child_stop_proven'] is False


def test_even_missing_task_terminal_notification_is_not_real_child_or_clear_evidence():
    result = PROBE['missing_task_observation']({
        'missing_task_stop_sent': True,
        'frames': [{'type': 'system', 'subtype': 'task_notification',
                    'probe_task_match': True, 'task_status': 'stopped'}],
    })
    assert result['matching_terminal_notifications'] == 1
    assert result['real_child_stop_proven'] is False
    assert result['durable_clear_proven'] is False


def test_missing_task_missing_or_malformed_response_is_unknown():
    for frames in (
        [],
        None,
        [None],
        [{'type': 'control_response', 'request_id': 'gate0-missing-stop'}],
        [{'type': 'control_response', 'request_id': 'gate0-missing-stop',
          'subtype': 'unexpected'}],
    ):
        result = PROBE['missing_task_observation']({
            'missing_task_stop_sent': True,
            'frames': frames,
        })
        assert result['control_response'] == 'unknown'
        assert result['real_child_stop_proven'] is False


def test_initialization_case_keeps_original_sdk_arguments_and_no_resume_id():
    PROBE['validate_selected_runtime']({
        'case': 'initialization',
        'resume_id': None,
        'arguments': PROBE['BASELINE_ARGUMENTS'][:],
    }, 'initialization')


def test_missing_parent_case_requires_sdk_derived_resume_uuid_and_argument_order():
    resume_id = '22222222-2222-4222-8222-222222222222'
    arguments = (PROBE['BASELINE_ARGUMENTS'][:5] + [f'--resume={resume_id}'] +
                 PROBE['BASELINE_ARGUMENTS'][5:])
    PROBE['validate_selected_runtime']({
        'case': 'missing-parent-resume',
        'resume_id': resume_id,
        'arguments': arguments,
    }, 'missing-parent-resume')


@pytest.mark.parametrize('case', ('positive-orphan', 'terminal-cleared'))
def test_selected_runtime_control_cases_keep_baseline_launch_shape(case):
    PROBE['validate_selected_runtime']({
        'case': case,
        'resume_id': None,
        'arguments': PROBE['BASELINE_ARGUMENTS'][:],
    }, case)


@pytest.mark.parametrize('resume_id', [
    None,
    'not-a-uuid',
    '22222222-2222-4222-7222-222222222222',
])
def test_missing_parent_case_rejects_missing_malformed_or_non_v4_resume(resume_id):
    with pytest.raises(RuntimeError, match='UUIDv4'):
        PROBE['validate_selected_runtime']({
            'case': 'missing-parent-resume',
            'resume_id': resume_id,
            'arguments': [],
        }, 'missing-parent-resume')


def test_missing_parent_case_has_no_stop_and_never_claims_exact_resume():
    result = PROBE['missing_parent_resume_observation']({
        'case': 'missing-parent-resume',
        'missing_task_stop_sent': False,
        'initialization': {
            'success': True,
            'error': True,
            'missing_parent_load_error': True,
            'session_identity_present': True,
            'session_identity_match': False,
        },
    })
    assert result == {
        'case': 'missing-parent-resume',
        'missing_task_stop_sent': False,
        'stop_control_forbidden': True,
        'init_success': True,
        'init_error': True,
        'missing_parent_load_error': True,
        'session_identity_present': True,
        'session_identity_match': False,
        'model_dispatch': 'unknown',
        'load_proven': False,
        'exact_resume_claim': False,
        'support_claim': False,
    }


def test_missing_parent_init_success_without_error_still_does_not_prove_load():
    result = PROBE['missing_parent_resume_observation']({
        'missing_task_stop_sent': False,
        'initialization': {'success': True, 'error': False},
    })
    assert result['init_success'] is True
    assert result['missing_parent_load_error'] is False
    assert result['model_dispatch'] == 'unknown'
    assert result['load_proven'] is False
    assert result['exact_resume_claim'] is False
    assert result['support_claim'] is False


@pytest.mark.parametrize('case', ('positive_orphan', 'terminal_cleared'))
def test_gate0_controls_are_explicitly_not_exercised_without_runtime_observation(case):
    result = PROBE['gate0_control_observation'](case)

    assert result == {
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


def test_gate0_control_observation_rejects_unknown_control_name():
    with pytest.raises(ValueError, match='unsupported Gate 0 control'):
        PROBE['gate0_control_observation']('unknown')


@pytest.mark.parametrize('case', ('positive_orphan', 'terminal_cleared'))
def test_selected_runtime_gate0_control_refuses_without_public_fixture_boundary(case):
    result = PROBE['runtime_control_refusal'](case)

    assert result['case'] == case
    assert result['status'] == 'unsupported'
    assert result['support_claim'] is False
    assert result['runtime_attempted'] is False
    assert result['selected_runtime_observed'] is False
    assert result['reason_codes'] == [
        'no-supported-public-fixture-boundary',
        'selected-runtime-control-refused-before-mutation',
    ]
