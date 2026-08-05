from __future__ import annotations

import csv
from copy import deepcopy
import json
from pathlib import Path

import pytest

from acoustic_encoder.config import load_config
from acoustic_encoder.mock_data import generate_dual_mode_mock
from acoustic_encoder.run_execution import execute_measurement_run
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    SourceFormat,
    artifact_sha256,
    load_spectrum,
)
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_REW = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "rew"
    / "external_reference"
    / "BW M1.txt"
)


def _multisine_run_case(tmp_path, **mock_options):
    stimulus = load_config(
        PROJECT_ROOT / "config" / "stimulus_multisine_broadband.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )["stimulus"]
    mock_root = tmp_path / "mock"
    mock_manifest_path = generate_dual_mode_mock(
        mock_root,
        deepcopy(stimulus),
        configurations=["U4ENC"],
        angles_deg=[0],
        random_state=123,
        recording_delay_samples=1379,
        **mock_options,
    )
    mock_manifest = json.loads(mock_manifest_path.read_text(encoding="utf-8"))
    sample = next(
        item
        for item in mock_manifest["samples"]
        if item["measurement_mode"] == "schroeder_multisine"
    )
    resolved = load_config(
        PROJECT_ROOT / "config" / "experiment_v2_u4_multisine.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    resolved["paths"]["stimuli"] = (mock_root / "stimuli").as_posix()
    return sample, resolved


def _edit_sidecar(sample, **updates) -> Path:
    path = Path(sample["sidecar_path"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(updates)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _external_reference_rew_case(tmp_path):
    meta = MeasurementMeta(
        sample_id="rew-reference-cc863c23f0f4",
        **SCHEMA_VERSION_QUARTET,
        device_version=None,
        configuration=None,
        angle_deg=None,
        session_id=None,
        repeat_type=None,
        repeat_id=None,
        experiment_step=None,
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.REW_TXT,
        source_path=EXTERNAL_REW.as_posix(),
        data_origin=DataOrigin.EXTERNAL_REFERENCE,
        dataset_role=DatasetRole.PARSER_FIXTURE,
        source_sha256=artifact_sha256(EXTERNAL_REW),
        provenance_uri="tests/fixtures/rew/external_reference/manifest.json",
        eligible_for_scientific_analysis=False,
    )
    metadata = tmp_path / "external-rew.json"
    metadata.write_text(json.dumps(meta.to_dict(), indent=2) + "\n", encoding="utf-8")
    resolved = load_config(
        PROJECT_ROOT / "config" / "experiment_v2_u4.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    return metadata, resolved


def test_clean_multisine_run_writes_reproducible_isolated_output_bundle(
    tmp_path,
) -> None:
    sample, resolved = _multisine_run_case(tmp_path)

    result = execute_measurement_run(
        sample["source_path"],
        sample["sidecar_path"],
        resolved,
        output_root=tmp_path / "outputs",
        run_id="clean-run",
    )

    expected_directory = (
        tmp_path
        / "outputs"
        / "simulated"
        / "software_validation"
        / "clean-run"
    )
    assert result.output_directory == expected_directory
    assert result.processing_status == "completed"
    assert result.success is True
    required = {
        "config_snapshot.yaml",
        "run_manifest.json",
        "run_manifest.sha256",
        "measurements.csv",
        "transfer_tones.csv",
        "tone_quality.csv",
        "clock_drift_qc.csv",
        "p8_measurement_qc.csv",
        "quality_control.csv",
        "qc_checks.csv",
        "measurement_qc.csv",
        "quality_control.json",
        "spectrum_data.npz",
        "spectrum_data.json",
        "synchronization_diagnostic.png",
        "period_consistency.png",
    }
    assert required.issubset(path.name for path in expected_directory.iterdir())
    manifest = json.loads(
        (expected_directory / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["success"] is True
    assert manifest["run_manifest_schema_version"] == "1.5.0"
    assert manifest["qc_schema_version"] == "1.0.0"
    assert manifest["versions"] == {
        "pipeline": "2.0.0-dev.11",
        "config_schema": "2.10.0",
        "measurement_schema": "2.4.0",
        "feature_schema": "2.2.0",
    }
    assert len(manifest["git"]["commit"]) == 40
    assert isinstance(manifest["git"]["dirty"], bool)
    assert manifest["measurement_mode"] == "schroeder_multisine"
    assert manifest["run_purpose"] == "software_validation"
    assert manifest["data_origin"] == "simulated"
    assert manifest["eligible_for_scientific_analysis"] is False
    assert manifest["phase_status"] == result.spectrum.phase_status.value
    assert manifest["qc_status"] == "valid"
    assert manifest["stimulus_id"] == sample["stimulus_id"]
    assert manifest["stimulus_hash"] == sample["stimulus_hash"]
    assert manifest["tone_set_id"] == sample["tone_set_id"]
    assert manifest["recording_hash"] == sample["source_sha256"]
    assert manifest["sidecar_hash"] == artifact_sha256(sample["sidecar_path"])
    assert manifest["config_hash"] == artifact_sha256(
        expected_directory / "config_snapshot.yaml"
    )
    assert manifest["created_at_utc"]
    assert manifest["finished_at_utc"]
    assert manifest["random_state"] == resolved["random_state"]
    assert manifest["stage_gate"]["P2"] == "completed"
    assert manifest["stage_gate"]["P3_A"] == "not_applicable_sparse"
    assert manifest["stage_gate"]["P3_B"] == "not_applicable_sparse"
    assert manifest["stage_gate"]["P3_C"] == "paired_run_required"
    assert manifest["stage_gate"]["P4_A"] == "analysis_scope_required"
    assert manifest["stage_gate"]["P4_B"] == "not_implemented"
    assert manifest["stage_gate"]["P5_P6"] == "not_implemented"
    assert "P4_P6" not in manifest["stage_gate"]
    for item in manifest["inputs"]:
        assert artifact_sha256(item["path"]) == item["sha256"]
    for item in manifest["artifacts"]:
        assert artifact_sha256(expected_directory / item["path"]) == item["sha256"]
    assert artifact_sha256(expected_directory / "run_manifest.json") == (
        expected_directory / "run_manifest.sha256"
    ).read_text(encoding="ascii").strip()
    restored = load_spectrum(expected_directory / "spectrum_data")
    assert restored.meta == result.spectrum.meta
    with (expected_directory / "transfer_tones.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        phase_states = {row["phase_status"] for row in csv.DictReader(handle)}
    assert phase_states == {result.spectrum.phase_status.value}


def test_official_rew_reference_dispatches_to_external_validation_partition(
    tmp_path,
) -> None:
    metadata, resolved = _external_reference_rew_case(tmp_path)

    result = execute_measurement_run(
        EXTERNAL_REW,
        metadata,
        resolved,
        output_root=tmp_path / "outputs",
        run_id="external-rew",
    )

    assert result.success is True
    assert result.output_directory == (
        tmp_path
        / "outputs"
        / "external_reference"
        / "software_validation"
        / "external-rew"
    )
    assert result.run_manifest["measurement_mode"] == "rew_sweep"
    assert result.run_manifest["eligible_for_scientific_analysis"] is False
    assert result.run_manifest["stage_gate"]["P8"] == "not_applicable"
    assert result.run_manifest["stage_gate"]["P2"] == "completed"
    assert result.run_manifest["stage_gate"]["P3_A"] == "completed"
    assert result.run_manifest["stage_gate"]["P3_B"] == "not_requested"
    assert result.run_manifest["stage_gate"]["P3_C"] == "paired_run_required"
    assert result.run_manifest["preprocessing"]["processing_status"] == "completed"
    assert result.run_manifest["preprocessing"]["preprocessing_id"].startswith(
        "sha256:"
    )
    assert (result.output_directory / "quality_control.json").is_file()
    assert (result.output_directory / "processed" / "feature_index.csv").is_file()
    assert (
        result.output_directory
        / "processed"
        / "preprocessing_manifest.json"
    ).is_file()
    assert (
        result.output_directory
        / "processed"
        / "features"
        / "dense_raw_spl"
        / f"{result.spectrum.meta.sample_id}.npz"
    ).is_file()
    assert load_spectrum(result.output_directory / "spectrum_data").meta == result.spectrum.meta


def test_dense_non_none_smoothing_is_recorded_as_completed_p3_b(tmp_path) -> None:
    metadata, resolved = _external_reference_rew_case(tmp_path)
    resolved["preprocessing"]["smoothing"] = {
        "method": "fractional_octave",
        "fraction_denominator": 3,
        "boundary": "truncate",
        "minimum_kernel_coverage": 0.4,
        "weighting_definition": "rectangular_uniform_linear_grid_db",
    }

    result = execute_measurement_run(
        EXTERNAL_REW,
        metadata,
        resolved,
        output_root=tmp_path / "outputs",
        run_id="external-rew-smoothed",
    )

    assert result.run_manifest["stage_gate"]["P3_A"] == "completed"
    assert result.run_manifest["stage_gate"]["P3_B"] == "completed"
    assert result.run_manifest["preprocessing"]["smoothing"]["method"] == (
        "fractional_octave"
    )


def test_official_rew_reference_is_blocked_from_research_partition(tmp_path) -> None:
    metadata, resolved = _external_reference_rew_case(tmp_path)
    resolved["run_purpose"] = "research_analysis"

    result = execute_measurement_run(
        EXTERNAL_REW,
        metadata,
        resolved,
        output_root=tmp_path / "outputs",
        run_id="external-rew-research",
    )

    assert result.processing_status == "blocked_research_gate"
    assert result.output_directory == (
        tmp_path
        / "outputs"
        / "external_reference"
        / "research_analysis"
        / "external-rew-research"
    )
    assert result.run_manifest["success"] is False
    assert result.run_manifest["failure"]["category"] == "research_gate"


def test_missing_sidecar_writes_quarantine_failure_manifest(tmp_path) -> None:
    source = tmp_path / "orphan.wav"
    source.write_bytes(b"not-a-real-wav")
    resolved = load_config(
        PROJECT_ROOT / "config" / "experiment_v2_u4_multisine.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )

    result = execute_measurement_run(
        source,
        tmp_path / "missing-sidecar.json",
        resolved,
        output_root=tmp_path / "outputs",
        run_id="missing-sidecar",
    )

    expected = tmp_path / "outputs" / "quarantine" / "missing-sidecar"
    assert result.output_directory == expected
    assert result.processing_status == "failed"
    assert result.success is False
    assert result.spectrum is None
    manifest = json.loads((expected / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["processing_status"] == "failed"
    assert manifest["success"] is False
    assert manifest["failure"]["category"] == "missing_input"
    assert manifest["failure"]["exception_type"] == "P1AdapterError"
    assert manifest["stage_gate"]["P4_A"] == "not_run"
    assert manifest["stage_gate"]["P4_B"] == "not_implemented"
    assert manifest["stage_gate"]["P5_P6"] == "not_implemented"
    assert (expected / "config_snapshot.yaml").is_file()
    assert (expected / "measurements.csv").is_file()
    assert (expected / "measurement_qc.csv").is_file()
    assert not (expected / "spectrum_data.npz").exists()


def test_research_analysis_rejects_simulated_input_with_gate_manifest(
    tmp_path,
) -> None:
    sample, resolved = _multisine_run_case(tmp_path)
    resolved["run_purpose"] = "research_analysis"

    result = execute_measurement_run(
        sample["source_path"],
        sample["sidecar_path"],
        resolved,
        output_root=tmp_path / "outputs",
        run_id="research-rejected",
    )

    assert result.processing_status == "blocked_research_gate"
    assert result.success is False
    assert result.spectrum is None
    assert result.run_manifest["failure"]["category"] == "research_gate"
    assert result.run_manifest["data_origin"] == "simulated"
    assert result.output_directory == (
        tmp_path
        / "outputs"
        / "simulated"
        / "research_analysis"
        / "research-rejected"
    )


def test_recording_hash_mismatch_writes_integrity_failure_manifest(tmp_path) -> None:
    sample, resolved = _multisine_run_case(tmp_path)
    recording = Path(sample["source_path"])
    recording.write_bytes(recording.read_bytes() + b"tampered")

    result = execute_measurement_run(
        recording,
        sample["sidecar_path"],
        resolved,
        output_root=tmp_path / "outputs",
        run_id="recording-hash-mismatch",
    )

    assert result.processing_status == "failed"
    assert result.spectrum is None
    assert result.run_manifest["failure"]["category"] == "integrity_mismatch"
    assert "recording hash mismatch" in result.run_manifest["failure"]["message"]
    assert not (result.output_directory / "spectrum_data.npz").exists()


def test_missing_canonical_stimulus_manifest_writes_failure_bundle(tmp_path) -> None:
    sample, resolved = _multisine_run_case(tmp_path)
    canonical_manifest = (
        Path(resolved["paths"]["stimuli"])
        / sample["stimulus_id"]
        / "stimulus_manifest.json"
    )
    canonical_manifest.unlink()

    result = execute_measurement_run(
        sample["source_path"],
        sample["sidecar_path"],
        resolved,
        output_root=tmp_path / "outputs",
        run_id="missing-manifest",
    )

    assert result.processing_status == "failed"
    assert result.run_manifest["failure"]["category"] == "missing_input"
    assert result.run_manifest["stage_gate"]["P8"] == "not_run"
    assert result.run_manifest["stage_gate"]["P4_A"] == "not_run"
    manifest_input = next(
        item
        for item in result.run_manifest["inputs"]
        if item["role"] == "stimulus_manifest"
    )
    assert manifest_input["exists"] is False
    assert manifest_input["sha256"] is None
    assert not (result.output_directory / "spectrum_data.npz").exists()


def test_stimulus_hash_mismatch_is_an_integrity_failure(tmp_path) -> None:
    sample, resolved = _multisine_run_case(tmp_path)
    sidecar = _edit_sidecar(sample, stimulus_hash="0" * 64)

    result = execute_measurement_run(
        sample["source_path"],
        sidecar,
        resolved,
        output_root=tmp_path / "outputs",
        run_id="stimulus-hash-mismatch",
    )

    assert result.run_manifest["failure"]["category"] == "integrity_mismatch"
    assert result.run_manifest["success"] is False


@pytest.mark.parametrize(
    ("config_key", "value", "expected_message"),
    [
        ("tone_set_id", "wrong-tone-set", "tone_set_id mismatch"),
        ("sample_rate_hz", 44100, "sample rate mismatch"),
    ],
)
def test_config_to_manifest_mismatch_is_an_artifact_failure(
    tmp_path,
    config_key,
    value,
    expected_message,
) -> None:
    sample, resolved = _multisine_run_case(tmp_path)
    resolved[config_key] = value

    result = execute_measurement_run(
        sample["source_path"],
        sample["sidecar_path"],
        resolved,
        output_root=tmp_path / "outputs",
        run_id=f"{config_key}-mismatch",
    )

    assert result.run_manifest["failure"]["category"] == "artifact_mismatch"
    assert expected_message in result.run_manifest["failure"]["message"]


def test_invalid_audio_channel_is_audited_without_analyzing(tmp_path) -> None:
    sample, resolved = _multisine_run_case(tmp_path)
    sidecar = _edit_sidecar(sample, audio_channel=1)

    result = execute_measurement_run(
        sample["source_path"],
        sidecar,
        resolved,
        output_root=tmp_path / "outputs",
        run_id="bad-channel",
    )

    assert result.run_manifest["failure"]["category"] == "validation_error"
    assert "channel 1 is unavailable" in result.run_manifest["failure"]["message"]


def test_unsupported_source_format_is_quarantined(tmp_path) -> None:
    sample, resolved = _multisine_run_case(tmp_path)
    sidecar = _edit_sidecar(sample, source_format="rew_txt")

    result = execute_measurement_run(
        sample["source_path"],
        sidecar,
        resolved,
        output_root=tmp_path / "outputs",
        run_id="bad-source-format",
    )

    assert result.output_directory == tmp_path / "outputs" / "quarantine" / "bad-source-format"
    assert result.run_manifest["failure"]["category"] == "validation_error"


def test_external_reference_cannot_masquerade_as_research_input(tmp_path) -> None:
    sample, resolved = _multisine_run_case(tmp_path)
    sidecar = _edit_sidecar(
        sample,
        data_origin="external_reference",
        dataset_role="research_input",
        eligible_for_scientific_analysis=True,
    )

    result = execute_measurement_run(
        sample["source_path"],
        sidecar,
        resolved,
        output_root=tmp_path / "outputs",
        run_id="reference-masquerade",
    )

    assert result.output_directory.parent.name == "quarantine"
    assert result.run_manifest["eligible_for_scientific_analysis"] is False
    assert result.run_manifest["failure"]["category"] == "validation_error"


def test_explicit_manual_review_reason_stops_before_p8(tmp_path) -> None:
    sample, resolved = _multisine_run_case(tmp_path)
    sidecar = _edit_sidecar(
        sample,
        manual_review_reasons=["unconfirmed_recording_identity"],
    )

    result = execute_measurement_run(
        sample["source_path"],
        sidecar,
        resolved,
        output_root=tmp_path / "outputs",
        run_id="manual-review",
    )

    assert result.processing_status == "manual_review_required"
    assert result.run_manifest["failure"]["category"] == "manual_review"
    assert result.run_manifest["failure"]["manual_review_reasons"] == [
        "unconfirmed_recording_identity"
    ]
    assert result.run_manifest["stage_gate"]["P8"] == "not_run"


def test_existing_output_directory_is_never_overwritten(tmp_path) -> None:
    sample, resolved = _multisine_run_case(tmp_path)
    first = execute_measurement_run(
        sample["source_path"],
        sample["sidecar_path"],
        resolved,
        output_root=tmp_path / "outputs",
        run_id="immutable-run",
    )
    first_hash = artifact_sha256(first.output_directory / "run_manifest.json")

    with pytest.raises(FileExistsError, match="already exists"):
        execute_measurement_run(
            sample["source_path"],
            sample["sidecar_path"],
            resolved,
            output_root=tmp_path / "outputs",
            run_id="immutable-run",
        )

    assert artifact_sha256(first.output_directory / "run_manifest.json") == first_hash


@pytest.mark.parametrize("run_id", [".", "..", "nested/run", "nested\\run", " "])
def test_run_id_cannot_escape_or_alias_the_isolated_output_directory(
    tmp_path,
    run_id,
) -> None:
    sample, resolved = _multisine_run_case(tmp_path)

    with pytest.raises(ValueError, match="one non-empty path component"):
        execute_measurement_run(
            sample["source_path"],
            sample["sidecar_path"],
            resolved,
            output_root=tmp_path / "outputs",
            run_id=run_id,
        )


def test_warning_qc_still_writes_complete_non_success_bundle(tmp_path) -> None:
    sample, resolved = _multisine_run_case(tmp_path)
    resolved["multisine_estimation"]["tone_quality"]["non_excited_energy"][
        "warning_ratio"
    ] = 0.0

    result = execute_measurement_run(
        sample["source_path"],
        sample["sidecar_path"],
        resolved,
        output_root=tmp_path / "outputs",
        run_id="qc-warning",
    )

    assert result.processing_status == "completed"
    assert result.success is False
    assert result.run_manifest["qc_status"] == "warning"
    assert (result.output_directory / "spectrum_data.npz").is_file()
    assert (result.output_directory / "measurement_qc.csv").is_file()


def test_exclude_qc_still_writes_complete_non_success_bundle(tmp_path) -> None:
    drift_ppm = 120.0
    sample, resolved = _multisine_run_case(
        tmp_path,
        sampling_clock_drift_ppm=drift_ppm,
    )

    result = execute_measurement_run(
        sample["source_path"],
        sample["sidecar_path"],
        resolved,
        output_root=tmp_path / "outputs",
        run_id=f"drift-{int(drift_ppm)}",
    )

    assert result.processing_status == "completed"
    assert result.success is False
    assert result.run_manifest["qc_status"] == "exclude_candidate"
    assert result.run_manifest["phase_status"] == "relative_unreliable"
    assert (result.output_directory / "spectrum_data.npz").is_file()
    assert (result.output_directory / "measurement_qc.csv").is_file()


def test_drift_correction_resegments_and_preserves_audited_phase_state(tmp_path) -> None:
    sample, resolved = _multisine_run_case(
        tmp_path,
        sampling_clock_drift_ppm=80.0,
    )
    resolved["multisine_estimation"]["clock_drift"]["correction"] = "enabled"

    result = execute_measurement_run(
        sample["source_path"],
        sample["sidecar_path"],
        resolved,
        output_root=tmp_path / "outputs",
        run_id="drift-corrected",
    )

    assert result.success is True
    assert result.spectrum.phase_status is PhaseStatus.DRIFT_CORRECTED
    drift = result.spectrum.quality_metrics["clock_drift"]
    assert drift["correction"]["applied"] is True
    assert drift["post_correction"]["absolute_residual_drift_ppm"] < 20.0


def test_run_never_mutates_source_sidecar_or_stimulus_inputs(tmp_path) -> None:
    sample, resolved = _multisine_run_case(tmp_path)
    sidecar = Path(sample["sidecar_path"])
    stimulus_manifest = (
        Path(resolved["paths"]["stimuli"])
        / sample["stimulus_id"]
        / "stimulus_manifest.json"
    )
    manifest_payload = json.loads(stimulus_manifest.read_text(encoding="utf-8"))
    stimulus_wav = stimulus_manifest.parent / manifest_payload["wav_file"]
    inputs = [Path(sample["source_path"]), sidecar, stimulus_manifest, stimulus_wav]
    before = [(artifact_sha256(path), path.stat().st_mtime_ns) for path in inputs]

    execute_measurement_run(
        sample["source_path"],
        sidecar,
        resolved,
        output_root=tmp_path / "outputs",
        run_id="read-only-inputs",
    )

    after = [(artifact_sha256(path), path.stat().st_mtime_ns) for path in inputs]
    assert after == before
