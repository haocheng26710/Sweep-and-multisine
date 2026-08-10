from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from acoustic_encoder.schemas import DataOrigin, DatasetRole, MeasurementMeta, MeasurementMode, SourceFormat
from acoustic_encoder.ui.experiment_plan import ExpectedSample, ExperimentRole
from acoustic_encoder.ui.sample_registry import (
    FinalTestSealedError,
    MatchStatus,
    ManualReviewDecision,
    SampleRegistry,
)


def _expected(sample_id: str = "s-plan-001", *, role: ExperimentRole = ExperimentRole.TRAINING) -> ExpectedSample:
    return ExpectedSample(
        sample_id=sample_id,
        condition_id="c-001",
        block_id="main",
        configuration_id="U4ENC",
        direction_id="D90",
        angle_deg=90.0,
        session_id="S01",
        repeat_type="CONT",
        repeat_id="CONT-001",
        reposition_round_id=None,
        assembly_id=None,
        acquisition_block_id="B01",
        measurement_mode=MeasurementMode.REW_SWEEP,
        experiment_role=role,
        stimulus_id=None,
        tone_set_id=None,
        sample_rate_hz=None,
        audio_channel=None,
    )


def _write_session(root: Path, *, angle: float = 90.0, source_bytes: bytes = b"rew data") -> tuple[Path, Path]:
    root.mkdir(parents=True)
    source = root / "input with spaces.txt"
    source.write_bytes(source_bytes)
    digest = hashlib.sha256(source_bytes).hexdigest()
    metadata = MeasurementMeta(
        sample_id="ui2-source-001",
        pipeline_version="2.0.0-dev.22",
        config_schema_version="2.21.0",
        measurement_schema_version="2.4.0",
        feature_schema_version="2.3.0",
        device_version="V2",
        configuration="U4ENC",
        angle_deg=angle,
        session_id="S01",
        repeat_type="CONT",
        repeat_id="CONT-001",
        experiment_step="TRAINING",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.MOCK_DENSE,
        source_path=source.as_posix(),
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256=digest,
        provenance_uri="records/provenance.json",
        eligible_for_scientific_analysis=False,
        acquisition_block_id="B01",
    )
    metadata_path = root / "measurement_metadata.json"
    metadata_path.write_text(json.dumps(metadata.to_dict()), encoding="utf-8")
    manifest = {
        "ui_session_schema_version": "1.0.0",
        "sample_id": metadata.sample_id,
        "run_id": "u2-test",
        "revision": 1,
        "route": "simulated_practice",
        "measurement_mode": "rew_sweep",
        "data_origin": "simulated",
        "dataset_role": "software_validation",
        "run_purpose": "software_validation",
        "eligible_for_scientific_analysis": False,
        "analysis_status": "ready",
        "analysis_block_reason": None,
        "git_commit": "a" * 40,
        "created_at_utc": "2026-08-10T12:00:00+00:00",
        "source_path": source.as_posix(),
        "metadata_path": metadata_path.as_posix(),
        "config_snapshot_path": (root / "resolved_config.yaml").as_posix(),
        "inputs": [{"path": source.as_posix(), "sha256": digest, "role": "source"}],
    }
    (root / "resolved_config.yaml").write_text("run_purpose: software_validation\n", encoding="utf-8")
    manifest_path = root / "ui_session_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (root / "ui_session_manifest.sha256").write_text(
        hashlib.sha256(manifest_path.read_bytes()).hexdigest(), encoding="ascii"
    )
    return manifest_path, source


def _write_run_output(root: Path, source_hash: str) -> Path:
    root.mkdir(parents=True)
    feature_json = root / "processed/dense_raw_spl.json"
    feature_json.parent.mkdir()
    feature_json.write_text('{"feature":"fixture"}', encoding="utf-8")
    feature_hash = hashlib.sha256(feature_json.read_bytes()).hexdigest()
    manifest = {
        "run_manifest_schema_version": "2.0.0",
        "processing_status": "completed",
        "success": True,
        "sample_id": "ui2-source-001",
        "measurement_mode": "rew_sweep",
        "data_origin": "simulated",
        "dataset_role": "software_validation",
        "run_purpose": "software_validation",
        "eligible_for_scientific_analysis": False,
        "recording_hash": source_hash,
        "qc_status": "valid",
        "artifacts": [{"path": "processed/dense_raw_spl.json", "sha256": feature_hash, "size_bytes": feature_json.stat().st_size}],
    }
    (root / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_explicit_session_registration_and_identity_match(tmp_path: Path) -> None:
    session, source = _write_session(tmp_path / "会话 one")
    output = _write_run_output(tmp_path / "输出 one", hashlib.sha256(source.read_bytes()).hexdigest())
    registry = SampleRegistry(tmp_path / "registry")

    registered = registry.register_ui2_session(session, expected=_expected(), output_directory=output)
    result = registry.match((_expected(),), (registered,))

    assert registered.feature_set_available is True
    assert registered.spectrum_data_available is False
    assert result.rows[0].status is MatchStatus.EXPECTED_AND_PRESENT
    assert result.rows[0].expected_sample_id == "s-plan-001"
    assert not hasattr(registry, "scan_directory")
    assert not hasattr(registry, "register_directory")


def test_missing_unexpected_duplicate_metadata_and_hash_mismatch(tmp_path: Path) -> None:
    registry = SampleRegistry(tmp_path / "registry")
    session1, source1 = _write_session(tmp_path / "s1")
    first = registry.register_ui2_session(session1, expected=_expected())
    session2, _ = _write_session(tmp_path / "s2", source_bytes=b"second")
    duplicate = registry.register_ui2_session(session2, expected=_expected())
    session3, _ = _write_session(tmp_path / "s3", angle=45.0, source_bytes=b"third")
    mismatch = registry.register_ui2_session(session3, expected=_expected("s-plan-002"))
    session4, _ = _write_session(tmp_path / "s4", source_bytes=b"fourth")
    unexpected = registry.register_ui2_session(session4)
    session5, source5 = _write_session(tmp_path / "s5", source_bytes=b"fifth")
    source5.write_bytes(b"changed before registration")
    changed = registry.register_ui2_session(session5, expected=_expected("s-plan-003"))

    result = registry.match(
        (_expected(), _expected("s-plan-002"), _expected("s-plan-003"), _expected("s-plan-004")),
        (first, duplicate, mismatch, unexpected, changed),
    )
    statuses = {row.expected_sample_id: row.status for row in result.rows if row.expected_sample_id}
    assert statuses["s-plan-001"] is MatchStatus.DUPLICATE_IDENTITY
    assert statuses["s-plan-002"] is MatchStatus.METADATA_MISMATCH
    assert statuses["s-plan-003"] is MatchStatus.HASH_MISMATCH
    assert statuses["s-plan-004"] is MatchStatus.EXPECTED_BUT_MISSING
    assert any(row.status is MatchStatus.UNEXPECTED_SAMPLE for row in result.rows)


def test_manual_review_is_append_only_and_does_not_mutate_metadata(tmp_path: Path) -> None:
    session, _ = _write_session(tmp_path / "session")
    metadata_path = tmp_path / "session/measurement_metadata.json"
    original = metadata_path.read_bytes()
    registry = SampleRegistry(tmp_path / "registry")
    registered = registry.register_ui2_session(session, expected=_expected())

    first = registry.append_manual_review(
        registered,
        ManualReviewDecision(
            operator="Reviewer",
            recorded_at="2026-08-10T13:00:00+01:00",
            reason="Investigated warning",
            decision="retain_for_software_validation",
            note="Automatic QC remains authoritative",
        ),
    )
    second = registry.append_manual_review(
        registered,
        ManualReviewDecision(
            operator="Reviewer 2",
            recorded_at="2026-08-10T14:00:00+01:00",
            reason="Second review",
            decision="manual_review_required",
            note=None,
        ),
    )

    assert first.audit_index == 1
    assert second.audit_index == 2
    assert len(registry.load_manual_reviews()) == 2
    assert metadata_path.read_bytes() == original


def test_final_test_binding_is_blocked_before_manifest_content_is_read(tmp_path: Path) -> None:
    manifest = tmp_path / "sealed/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("this is deliberately not JSON", encoding="utf-8")
    registry = SampleRegistry(tmp_path / "registry")

    with pytest.raises(FinalTestSealedError):
        registry.register_ui2_session(
            manifest,
            expected=_expected(role=ExperimentRole.FINAL_TEST_SEALED),
        )

    incidents = registry.load_final_test_incidents()
    assert len(incidents) == 1
    assert incidents[0]["selected_path"] == manifest.resolve().as_posix()
    assert incidents[0]["content_read"] is False


def test_real_multisine_registration_remains_blocked(tmp_path: Path) -> None:
    expected = replace(
        _expected(),
        measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        stimulus_id="stim-1",
        tone_set_id="tones-1",
        sample_rate_hz=48000,
        audio_channel=0,
    )
    registry = SampleRegistry(tmp_path / "registry")
    decision = registry.mode_gate(
        data_origin=DataOrigin.REAL_EXPERIMENT,
        expected=expected,
    )
    assert decision.allowed is False
    assert "真实 Multisine" in decision.reason
