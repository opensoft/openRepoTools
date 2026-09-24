# SPDX-License-Identifier: Apache-2.0
"""Offline safety contracts for the one-shot volume metadata candidate."""

import json
import os
from pathlib import Path
import runpy

import pytest


SCANNER = runpy.run_path(
    str(Path(__file__).parent / "probes" / "inspect_two_domain_volume_metadata.py")
)
SCANNER_GLOBALS = SCANNER["scan_tree"].__globals__


def test_two_domain_metadata_reports_oversized_sparse_file_without_reading_bytes(tmp_path, monkeypatch):
    (tmp_path / "boundary.bin").write_bytes(b"")
    with (tmp_path / "boundary.bin").open("r+b") as handle:
        handle.truncate(65_536)
    (tmp_path / "large.bin").write_bytes(b"")
    with (tmp_path / "large.bin").open("r+b") as handle:
        handle.truncate(70_000)

    def content_read_is_forbidden(*_args, **_kwargs):
        raise AssertionError("metadata diagnostic attempted to read file bytes")

    monkeypatch.setattr(SCANNER["os"], "read", content_read_is_forbidden)
    report = SCANNER["scan_tree"](str(tmp_path))

    assert report["status"] == "complete"
    assert report["private"]["total_file_bytes"] == 135_536
    assert report["private"]["max_file_bytes"] == 70_000
    assert report["private"]["over_65536_files"] == [
        {"path": "large.bin", "kind": "file", "size": 70_000}
    ]
    assert report["public"]["category"] == "oversized-files-observed"
    assert report["public"]["over_65536_file_count"] == 1
    assert "large.bin" not in json.dumps(report["public"])


@pytest.mark.parametrize(
    ("entry_kind", "reason"),
    [
        ("symlink", "metadata-symlink-entry"),
        ("hardlink", "metadata-hardlink-entry"),
        ("fifo", "metadata-nonregular-entry"),
    ],
)
def test_two_domain_metadata_refuses_links_and_nonregular_entries(tmp_path, entry_kind, reason):
    target = tmp_path / "target"
    target.write_text("fixture", encoding="utf-8")
    entry = tmp_path / "entry"
    if entry_kind == "symlink":
        entry.symlink_to(target)
    elif entry_kind == "hardlink":
        os.link(target, entry)
    else:
        os.mkfifo(entry)

    with pytest.raises(SCANNER["MetadataRefusal"]) as raised:
        SCANNER["scan_tree"](str(tmp_path))
    assert raised.value.code == reason


@pytest.mark.parametrize(
    ("limit_name", "limit", "tree", "reason"),
    [
        ("MAX_FILES", 1, "two-files", "metadata-file-limit"),
        ("MAX_ENTRIES", 1, "dir-and-file", "metadata-entry-limit"),
        ("MAX_DEPTH", 1, "nested", "metadata-depth-limit"),
        ("MAX_PATH_BYTES", 3, "long-name", "metadata-path-limit"),
    ],
)
def test_two_domain_metadata_enforces_structural_bounds(tmp_path, monkeypatch, limit_name, limit, tree, reason):
    monkeypatch.setitem(SCANNER_GLOBALS, limit_name, limit)
    if tree == "two-files":
        (tmp_path / "a").touch()
        (tmp_path / "b").touch()
    elif tree == "dir-and-file":
        (tmp_path / "child").mkdir()
        (tmp_path / "file").touch()
    elif tree == "nested":
        (tmp_path / "one").mkdir()
        (tmp_path / "one" / "two").mkdir()
    else:
        (tmp_path / "long").touch()

    with pytest.raises(SCANNER["MetadataRefusal"]) as raised:
        SCANNER["scan_tree"](str(tmp_path))
    assert raised.value.code == reason


def test_two_domain_metadata_detects_file_mutation_during_stat_walk(tmp_path, monkeypatch):
    target = tmp_path / "mutate-me"
    target.write_text("before", encoding="utf-8")
    original_fstat = os.fstat
    seen_regular = 0

    def mutate_after_opened_stat(fd):
        nonlocal seen_regular
        value = original_fstat(fd)
        if os.path.samefile(f"/proc/self/fd/{fd}", target):
            seen_regular += 1
            if seen_regular == 2:
                with target.open("a", encoding="utf-8") as handle:
                    handle.write("-changed")
        return value

    monkeypatch.setattr(SCANNER["os"], "fstat", mutate_after_opened_stat)
    with pytest.raises(SCANNER["MetadataRefusal"]) as raised:
        SCANNER["scan_tree"](str(tmp_path))
    assert raised.value.code in {
        "metadata-file-revalidation-failed",
        "metadata-file-mutated",
    }


def test_two_domain_metadata_enforces_monotonic_walltime_bound(tmp_path, monkeypatch):
    (tmp_path / "item").touch()
    ticks = iter((10.0, 12.0))
    monkeypatch.setattr(SCANNER["time"], "monotonic", lambda: next(ticks))
    with pytest.raises(SCANNER["MetadataRefusal"]) as raised:
        SCANNER["scan_tree"](str(tmp_path), wall_seconds=1.0)
    assert raised.value.code == "metadata-walltime-limit"


def test_two_domain_metadata_checks_deadline_per_revalidation_and_before_summary(tmp_path, monkeypatch):
    (tmp_path / "one").write_text("x", encoding="utf-8")
    original = SCANNER_GLOBALS["_check_deadline"]
    checks = []

    def count_checks(deadline):
        checks.append(deadline)
        original(deadline)

    monkeypatch.setitem(SCANNER_GLOBALS, "_check_deadline", count_checks)
    SCANNER["scan_tree"](str(tmp_path))
    # With one file and the root directory, this includes a check before and
    # after each revalidation syscall, plus checks around summary creation.
    assert len(checks) >= 9


def test_two_domain_metadata_deadline_covers_json_serialization(tmp_path, monkeypatch, capsys):
    report = SCANNER["_refusal_report"]("metadata-io-refused")
    monkeypatch.setattr(SCANNER["time"], "monotonic", lambda: 10.0)
    emitted = SCANNER["_emit_json"](report, deadline=9.0)
    output = capsys.readouterr().out.encode("ascii")
    assert emitted is False
    assert json.loads(output)["private"]["reason_code"] == "metadata-walltime-limit"


def test_two_domain_metadata_public_projection_recomputes_and_strips_paths(tmp_path):
    (tmp_path / "private-name.jsonl").write_text("x", encoding="utf-8")
    report = SCANNER["scan_tree"](str(tmp_path))
    private_path = tmp_path / "private-report.json"
    private_path.write_text(json.dumps(report), encoding="utf-8")

    public = SCANNER["_read_public_projection"](str(private_path))
    assert public == report["public"]
    assert "private-name.jsonl" not in json.dumps(public)

    forged = dict(report)
    forged["public"] = dict(report["public"], category="private-name.jsonl")
    private_path.write_text(json.dumps(forged), encoding="utf-8")
    with pytest.raises(SCANNER["MetadataRefusal"]):
        SCANNER["_read_public_projection"](str(private_path))

    malformed = dict(report)
    malformed["private"] = dict(report["private"])
    malformed["private"]["entries"] = [{"path": "ok", "kind": [], "size": 1}]
    private_path.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(SCANNER["MetadataRefusal"]):
        SCANNER["_read_public_projection"](str(private_path))

    malformed_status = dict(report, status=[])
    private_path.write_text(json.dumps(malformed_status), encoding="utf-8")
    with pytest.raises(SCANNER["MetadataRefusal"]):
        SCANNER["_read_public_projection"](str(private_path))

    private_path.write_text('{"schema":"x","schema":"y"}', encoding="utf-8")
    with pytest.raises(SCANNER["MetadataRefusal"]):
        SCANNER["_read_public_projection"](str(private_path))


def test_two_domain_metadata_output_is_bounded_and_never_rejects_size_alone(tmp_path, monkeypatch, capsys):
    (tmp_path / "not-a-refusal.bin").write_bytes(b"")
    with (tmp_path / "not-a-refusal.bin").open("r+b") as handle:
        handle.truncate(600_000)
    report = SCANNER["scan_tree"](str(tmp_path))
    assert report["status"] == "complete"
    assert report["public"]["total_file_bytes"] == 600_000

    monkeypatch.setitem(SCANNER_GLOBALS, "MAX_OUTPUT_BYTES", 512)
    emitted = SCANNER["_emit_json"](report)
    output = capsys.readouterr().out.encode("ascii")
    assert emitted is False
    assert len(output) <= 512
    assert json.loads(output)["private"]["reason_code"] == "metadata-output-limit"
