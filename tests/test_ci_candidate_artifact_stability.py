# SPDX-License-Identifier: Apache-2.0
"""Admission publication races never supply proof; only fresh stable reads do."""

import copy
import json
from types import SimpleNamespace

import pytest

from test_ci_candidate_metadata import candidate, route
from test_ci_cutover import artifact, batch, cutover, delivery, install_artifact, request_for


@pytest.mark.parametrize('change', ['metadata', 'queued-to-running', 'running-to-completed'])
def test_ci_candidate_artifact_stability_caller_movement_reobserves_full_proof(
        cutover, batch, candidate, change):
    caller = batch['data']['actions/runs/601']
    caller.update(status='queued' if change == 'queued-to-running' else 'in_progress', conclusion=None)
    expected = route(cutover, batch, candidate)
    assert expected['mode'] == 'candidate' and expected['omit_full'] is True
    reader, reads = request_for(batch), []

    def request(repo, endpoint):
        if endpoint == 'actions/runs/601':
            reads.append(True)
            if len(reads) == 2:  # The artifact reader's own final caller read.
                caller['updated_at'] = '2026-11-16T14:47:23Z'
                if change == 'queued-to-running':
                    caller['status'] = 'in_progress'
                elif change == 'running-to-completed':
                    caller.update(status='completed', conclusion='success')
        return reader(repo, endpoint)

    observed = route(cutover, batch, candidate, request)
    assert observed == {**cutover.FULL, 'retryable': True}
    assert len(reads) == 2 and 'proof' not in observed
    # The next observation must authenticate the real archive and source proof
    # again. Movement is not ignored and no old observation is accepted.
    assert route(cutover, batch, candidate) == expected


@pytest.mark.parametrize('change', ['failed', 'cancelled', 'rerun', 'actor', 'triggering-actor',
                                   'head', 'branch', 'id', 'path', 'repository', 'unknown-status',
                                   'pending-with-conclusion'])
def test_ci_candidate_artifact_stability_invalid_caller_never_waits(
        cutover, batch, candidate, change):
    caller, reader, reads = batch['data']['actions/runs/601'], request_for(batch), []

    def request(repo, endpoint):
        if endpoint == 'actions/runs/601':
            reads.append(True)
            if len(reads) == 2:
                if change in {'failed', 'cancelled'}:
                    caller.update(status='completed', conclusion='failure' if change == 'failed' else 'cancelled')
                elif change == 'rerun':
                    caller['run_attempt'] = 2
                elif change in {'actor', 'triggering-actor'}:
                    caller[change.replace('-', '_')]['login'] = 'not-mergify'
                elif change == 'head':
                    caller['head_sha'] = 'f' * 40
                elif change == 'branch':
                    caller['head_branch'] = 'mergify/merge-queue/abcdef0123'
                elif change == 'id':
                    caller['id'] = 902
                elif change == 'path':
                    caller['path'] = '.github/workflows/untrusted.yml'
                elif change == 'repository':
                    caller['repository']['id'] = 1
                elif change == 'pending-with-conclusion':
                    caller.update(status='in_progress', conclusion='failure')
                else:
                    caller['status'] = 'unknown'
        return reader(repo, endpoint)

    assert route(cutover, batch, candidate, request) == cutover.FULL
    assert len(reads) == 2


@pytest.mark.parametrize('failure', ['artifact', 'digest', 'review'])
def test_ci_candidate_artifact_stability_next_observation_cannot_borrow_old_proof(
        cutover, batch, candidate, failure):
    caller, reader, reads = batch['data']['actions/runs/601'], request_for(batch), []

    def request(repo, endpoint):
        if endpoint == 'actions/runs/601':
            reads.append(True)
            if len(reads) == 2:
                caller['display_title'] = 'New caller description'
        return reader(repo, endpoint)

    assert route(cutover, batch, candidate, request) == {**cutover.FULL, 'retryable': True}
    if failure == 'artifact':
        batch['data']['actions/runs/601/artifacts?per_page=100&page=1']['artifacts'] = []
        batch['data']['actions/runs/601/artifacts?per_page=100&page=1']['total_count'] = 0
        # Completed callers without a receipt are not authenticated pending.
        caller.update(status='completed', conclusion='success')
    elif failure == 'digest':
        batch['data']['actions/artifacts/701']['digest'] = 'sha256:' + '0' * 64
    else:
        batch['data']['issues/7/comments?per_page=100'] = []
    assert route(cutover, batch, candidate) == cutover.FULL


def test_ci_candidate_artifact_stability_pending_diagnostic_has_no_values(
        cutover, batch, candidate, capsys):
    secret = 'Private caller title must not reach logs'
    caller, reader, reads = batch['data']['actions/runs/601'], request_for(batch), []

    def request(repo, endpoint):
        if endpoint == 'actions/runs/601':
            reads.append(True)
            if len(reads) == 2:
                caller['display_title'] = secret
        return reader(repo, endpoint)

    assert route(cutover, batch, candidate, request) == {**cutover.FULL, 'retryable': True}
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert [json.loads(line) for line in captured.err.splitlines()] == [{
        'delivery_diagnostic': 'admission-caller-reread-pending', 'stage': 'candidate'}]


@pytest.mark.parametrize('phase,allow_pending', [
    ('admission', False), ('qualified', False), ('qualified', True),
])
def test_ci_candidate_artifact_stability_non_pending_read_remains_strict(
        cutover, batch, artifact, phase, allow_pending):
    data, _row = install_artifact(cutover, batch, artifact, phase)
    original, reader = copy.deepcopy(artifact['run']), request_for(batch)

    def request(repo, endpoint):
        if endpoint == 'actions/runs/601':
            batch['data'][endpoint]['updated_at'] = '2026-11-16T14:47:23Z'
        return reader(repo, endpoint)

    with pytest.raises(cutover.verifier.Refused) as refused:
        cutover.evidence.artifact_record(original, phase, request, lambda _id: data,
                                         allow_pending=allow_pending)
    assert not isinstance(refused.value, cutover.verifier.PendingEvidence)


def test_ci_candidate_artifact_stability_changed_artifact_never_waits(cutover, batch, candidate):
    reader = request_for(batch)

    def request(repo, endpoint):
        result = reader(repo, endpoint)
        if endpoint == 'actions/artifacts/701':
            result['digest'] = 'sha256:' + '0' * 64
            batch['data']['actions/runs/601']['updated_at'] = '2026-11-16T14:47:23Z'
        return result

    assert route(cutover, batch, candidate, request) == cutover.FULL


@pytest.mark.parametrize('settles', [True, False])
def test_ci_candidate_artifact_stability_uses_existing_observation_budget(
        cutover, batch, candidate, monkeypatch, settles):
    expected = route(cutover, batch, candidate)
    caller, reader, reads, sleeps = batch['data']['actions/runs/601'], request_for(batch), [], []
    monkeypatch.setattr(cutover, 'PENDING_ATTEMPTS', 2)
    monkeypatch.setattr(cutover, 'time', SimpleNamespace(sleep=sleeps.append))

    def request(repo, endpoint):
        if endpoint == 'actions/runs/601':
            reads.append(True)
            if len(reads) == 2 or (not settles and len(reads) % 2 == 0):
                caller['display_title'] = 'Description revision ' + str(len(reads))
        return reader(repo, endpoint)

    observed = cutover.bounded_observation(lambda: route(cutover, batch, candidate, request))
    if settles:
        assert observed == expected and sleeps == [10]
    else:
        assert observed == {**cutover.FULL, 'retryable': True}
        assert sleeps == [10, 10] and len(reads) == 6 and 'proof' not in observed
