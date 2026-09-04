import importlib.util
from pathlib import Path

import pytest
import numpy as np


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("r256", HERE / "run_resumable_256_gate.py")
R256 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(R256)


def make_completed_chunk(directory, frequencies):
    directory.mkdir(parents=True)
    f = np.asarray(frequencies)
    np.savez_compressed(directory / "fields.npz", frequency=f, mic=np.ones(f.size, complex),
                        e_all=np.ones(f.size), e_hr03=np.ones(f.size),
                        e_south=np.ones(f.size), e_plenum=np.ones(f.size))
    for name in ("fields.csv", "chunk_record.json", "validation.json", "model.mph", "execution.log"):
        (directory / name).write_text("{}", encoding="utf-8")
    R256.write_checksums(directory)


def test_empty_state_starts_at_coarse_chunk_zero(tmp_path):
    contract = R256.build_contract_for_tests()
    decision = R256.next_chunk(contract, {"completed": {"coarse": [], "fine": []}})
    assert decision == ("coarse", 0)


def test_completed_chunk_is_skipped_when_state_records_it():
    contract = R256.build_contract_for_tests()
    decision = R256.next_chunk(contract, {"completed": {"coarse": [0], "fine": []}})
    assert decision == ("coarse", 1)


def test_partial_chunk_is_archived_and_only_that_chunk_is_prepared(tmp_path):
    partial = tmp_path / ".chunk_002.partial"
    partial.mkdir()
    (partial / "evidence.txt").write_text("interrupted", encoding="utf-8")
    archived = R256.prepare_partial_for_rerun(partial)
    assert archived is not None and archived.exists()
    assert (archived / "evidence.txt").read_text(encoding="utf-8") == "interrupted"
    assert not partial.exists()


def test_completed_chunk_missing_file_or_bad_hash_stops_immediately(tmp_path):
    frequencies = R256.frozen_frequencies()[:64]
    directory = tmp_path / "chunk_000.completed"
    make_completed_chunk(directory, frequencies)
    (directory / "model.mph").unlink()
    with pytest.raises(R256.CheckpointIntegrityError, match="missing files"):
        R256.verify_chunk_directory(directory, frequencies)
    make_completed_chunk(tmp_path / "bad.completed", frequencies)
    (tmp_path / "bad.completed" / "fields.csv").write_text("tampered", encoding="utf-8")
    with pytest.raises(R256.CheckpointIntegrityError, match="hash mismatch"):
        R256.verify_chunk_directory(tmp_path / "bad.completed", frequencies)


def test_frequency_or_frozen_contract_change_stops(tmp_path, monkeypatch):
    frequencies = R256.frozen_frequencies()[:64]
    directory = tmp_path / "chunk.completed"
    make_completed_chunk(directory, frequencies)
    with pytest.raises(R256.CheckpointIntegrityError, match="frequency mismatch"):
        R256.verify_chunk_directory(directory, list(reversed(frequencies)))
    contract_file = tmp_path / "frozen.json"
    contract_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(R256, "CONTRACT_PATH", contract_file)
    with pytest.raises(R256.CheckpointIntegrityError, match="contract hash mismatch"):
        R256.verify_checkpoints(R256.build_contract_for_tests(), {"contract_sha256": "changed", "completed": {"coarse": [], "fine": []}})


def test_fine_cannot_start_before_all_coarse_chunks(tmp_path, monkeypatch):
    contract_file = tmp_path / "frozen.json"
    contract_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(R256, "CONTRACT_PATH", contract_file)
    state = {"contract_sha256": R256.sha256(contract_file), "completed": {"coarse": [0, 1, 2], "fine": [0]}}
    with pytest.raises(R256.CheckpointIntegrityError, match="before all coarse"):
        R256.verify_checkpoints(R256.build_contract_for_tests(), state)


def test_partial_directory_is_atomically_renamed_to_completed(tmp_path):
    partial = tmp_path / ".chunk.partial"
    completed = tmp_path / "chunk.completed"
    partial.mkdir()
    (partial / "proof").write_text("complete", encoding="utf-8")
    R256.commit_partial(partial, completed)
    assert not partial.exists()
    assert (completed / "proof").read_text(encoding="utf-8") == "complete"


def test_every_frozen_index_is_covered_exactly_once_for_each_mesh():
    contract = R256.build_contract_for_tests()
    for mesh, expected_chunks in (("coarse", 4), ("fine", 16)):
        chunks = contract["chunks"][mesh]
        indices = [index for chunk in chunks for index in range(chunk["start_index"], chunk["end_index_inclusive"] + 1)]
        frequencies = [value for chunk in chunks for value in chunk["frequencies_hz"]]
        assert len(chunks) == expected_chunks
        assert indices == list(range(256))
        assert frequencies == contract["frequencies_hz"]


def test_interrupted_solved_partial_counts_actual_solved_and_uncommitted(tmp_path, monkeypatch):
    partial = tmp_path / ".chunk_000.partial"
    partial.mkdir()
    (partial / "execution.log").write_text("study.run start now\nstudy.run complete later\n", encoding="utf-8")
    monkeypatch.setattr(R256, "partial_dir", lambda mesh, index: partial)
    state = {"completed": {"coarse": [], "fine": []}, "study_run_count": 0}
    R256.ensure_provenance_counters(state)
    assert state["actual_study_run_submissions"] == 1
    assert state["successfully_solved_study_runs"] == 1
    assert state["atomically_committed_chunks"] == 0
    assert state["study_run_count"] == 1


def test_validated_partial_releases_resources_before_atomic_rename(tmp_path, monkeypatch):
    partial = tmp_path / ".chunk.partial"
    completed = tmp_path / "chunk.completed"
    partial.mkdir()
    events = []
    locked = {"value": True}

    def release():
        events.append("release")
        locked["value"] = False

    original_commit = R256.commit_partial

    def guarded_commit(source, target):
        events.append("rename")
        if locked["value"]:
            raise PermissionError("simulated Windows open-file lock")
        original_commit(source, target)

    monkeypatch.setattr(R256, "commit_partial", guarded_commit)
    R256.release_then_commit_validated_partial(partial, completed, release)
    assert events == ["release", "rename"]
    assert completed.exists() and not partial.exists()


def test_each_chunk_is_dispatched_to_a_fresh_python_worker(monkeypatch):
    calls = []

    def fake_run(command, **options):
        calls.append((command, options))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(R256.subprocess, "run", fake_run)
    R256.dispatch_chunk_worker(cores=3)
    R256.dispatch_chunk_worker(cores=3)

    assert len(calls) == 2
    for command, options in calls:
        assert command == [
            R256.sys.executable,
            str(R256.SCRIPT),
            "--resume",
            "--cores",
            "3",
            "--single-chunk-worker",
        ]
        assert options == {"check": False}


def test_preload_integrity_failure_never_overwrites_existing_checkpoint(tmp_path, monkeypatch):
    state_path = tmp_path / "resume_state.json"
    original = '{"actual_study_run_submissions": 2, "atomically_committed_chunks": 2}\n'
    state_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(R256, "STATE_PATH", state_path)

    persisted = R256.persist_checkpoint_integrity_failure(None, R256.CheckpointIntegrityError("preload failure"))

    assert persisted is False
    assert state_path.read_text(encoding="utf-8") == original
