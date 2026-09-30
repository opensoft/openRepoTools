# SPDX-License-Identifier: Apache-2.0
"""Offline control boundaries; no Claude account or model request is made."""

import json
import socket
import subprocess
import threading

import pytest

from lane_managed_cli_control import (LaneCliControlService, _runtime_socket,
                                      _project_git_identity, control_request)
from lane_managed_state import ManagedStateError
from test_lane_managed_state import _store


def test_control_request_uses_private_credential_and_exact_payload(tmp_path):
    credential = tmp_path / "credential.json"
    credential.write_text('{"token":"scoped-secret"}')
    credential.chmod(0o600)
    endpoint = tmp_path / "control.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(endpoint))
    server.listen(1)
    seen = []

    def answer():
        connection, _ = server.accept()
        with connection:
            raw = bytearray()
            while not raw.endswith(b"\n"):
                raw.extend(connection.recv(4096))
            seen.append(json.loads(raw))
            connection.sendall(b'{"ok":true,"result":{"operation_id":"swap-exact"}}\n')

    worker = threading.Thread(target=answer)
    worker.start()
    try:
        result = control_request(endpoint, credential, "prepare",
                                 {"parent_uuid": "parent", "runtime_id": "runtime"})
    finally:
        worker.join(timeout=3)
        server.close()
    assert result == {"operation_id": "swap-exact"}
    assert seen == [{"credential": "scoped-secret", "method": "prepare",
                     "payload": {"parent_uuid": "parent", "runtime_id": "runtime"}}]


def test_start_requires_explicit_worktree_before_any_enrollment(tmp_path):
    service = LaneCliControlService.__new__(LaneCliControlService)
    service.config_file = tmp_path / "session.json"
    with pytest.raises(ManagedStateError, match="start fields are malformed"):
        service._start({"source_profile": "A", "target_profile": "B",
                        "parent_uuid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"})
    assert not service.config_file.exists()


def test_project_identity_resolves_subdirectory_of_separate_git_repository(tmp_path):
    state = tmp_path / "wip-state"
    project = tmp_path / "actual-project"
    for path in (state, project):
        subprocess.run(["git", "init", "-q", str(path)], check=True)
    nested = project / "src"
    nested.mkdir()
    top, common = _project_git_identity(nested)
    assert top == project
    assert common == project / ".git"
    assert common != state / ".git"


def test_project_identity_rejects_non_git_directory_before_enrollment(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(ManagedStateError, match="not a project Git worktree"):
        _project_git_identity(plain)


def test_separate_project_root_claim_blocks_another_lane(managed_workspace):
    first = _store(managed_workspace, lane="project-claim-a")
    second = _store(managed_workspace, lane="project-claim-b")
    project = managed_workspace.project.resolve()
    worktree, repository = _project_git_identity(project)
    assert first.identity.common_dir != repository
    a = first.enroll_managed("daemon-project-a", lineage_id="project-lineage-a")
    b = second.enroll_managed("daemon-project-b", lineage_id="project-lineage-b")
    claim = first.claim_lineage_workspace(
        lineage_id="project-lineage-a", owner_generation=a["generation"],
        lineage_generation=1, workspace=str(worktree),
        common_dir=str(first.identity.common_dir), repository=str(repository))
    assert claim["workspace"] == str(project)
    assert claim["common_dir"] == str(managed_workspace.common_dir)
    assert claim["repository"] == str(repository)
    with pytest.raises(ManagedStateError) as refused:
        second.claim_lineage_workspace(
            lineage_id="project-lineage-b", owner_generation=b["generation"],
            lineage_generation=1, workspace=str(worktree),
            common_dir=str(second.identity.common_dir), repository=str(repository))
    assert refused.value.code == "ownership-conflict"


def test_read_only_socket_resolution_does_not_create_runtime_root(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    with pytest.raises(ManagedStateError, match="control socket directory is unavailable"):
        _runtime_socket("lane identity", create=False)
    assert list(tmp_path.iterdir()) == []


def test_lost_response_ack_does_not_raise_from_service():
    sender, receiver = socket.socketpair()
    try:
        receiver.close()
        assert LaneCliControlService._send_response(sender, {"ok": True, "result": {}}) is False
    finally:
        sender.close()
