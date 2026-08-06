from __future__ import annotations

import json

import pytest

from acoustic_encoder.dataset_quality_control import DatasetQCReference, feature_set_content_sha256
from acoustic_encoder.hr_analysis import FinalTestSeal
from acoustic_encoder.hr_readout import (
    CalibrationResonatorWindow,
    HRCalibrationReference,
    HRReadoutAnalysis,
    HRReadoutResult,
    HRReadoutScope,
    HRReadoutScopeMember,
    build_hr_feature_sets,
    readout_multisine_feature,
)
from acoustic_encoder.hr_readout_outputs import (
    load_hr_readout_bundle,
    write_hr_readout_outputs,
)
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import DataOrigin, DatasetRole, artifact_sha256
from test_hr_readout import _digest, _readout_config, _tone_feature


def _analysis_fixture():
    source = _tone_feature((1000.0,), (10.0,))
    sample = readout_multisine_feature(
        source,
        (CalibrationResonatorWindow("R1", 1000.0, 1000.0, 1000.0, "nearest_tone"),),
        _readout_config("nearest_tone"),
    )
    calibration = HRCalibrationReference(
        _digest("7"), "calibration.json", "8" * 64,
        "manifest.json", "9" * 64, "manifest.sha256", "a" * 64,
    )
    member = HRReadoutScopeMember(
        source.sample_id, "features/ms-1", "1" * 64, "2" * 64,
        feature_set_content_sha256(source), _digest("4"), "U4ENC", "A000", 0.0,
        "S01", "CONT", DatasetRole.SOFTWARE_VALIDATION, "explicit fixture",
        source.tone_set_id, source.tone_set_sha256, source.meta.stimulus_id,
        source.meta.stimulus_hash, source.source_magnitude_quantity,
        source.source_magnitude_reference, "development",
    )
    scope = HRReadoutScope(
        "1.0.0", "P6B-OUTPUT", (member,), calibration, "G1", ("R1",),
        "nearest_tone", "nearest_tone_power",
        DatasetQCReference("P2B-OUTPUT", _digest("b")),
        FinalTestSeal(True, ("final-1",), _digest("c")),
        RunPurpose.SOFTWARE_VALIDATION, DataOrigin.SIMULATED,
        DatasetRole.SOFTWARE_VALIDATION, 20260806,
    )
    result = HRReadoutResult(
        "1.0.0", scope.hr_readout_scope_id, scope.sha256, _digest("d"),
        calibration.calibration_id, calibration.calibration_json_sha256,
        calibration.calibration_manifest_sha256, "software_validation_only",
        scope.p2b_reference.dataset_qc_result_sha256,
        scope.p2b_reference.analysis_scope_id, "valid", True,
        "software_validation", "simulated", "software_validation",
        "software_validation_only", False, False, False, False,
        "no_cross_mode_amplitude_calibration", "magnitude_only", "unavailable",
        "2026-08-06T12:00:00+00:00", (source.sample_id,),
        (feature_set_content_sha256(source),), (sample,), (),
    )
    energy, fractions = build_hr_feature_sets(
        (source,), result, scope, _readout_config("nearest_tone")
    )
    return HRReadoutAnalysis(result, energy, fractions), scope


def test_hr_readout_bundle_round_trip_hashes_and_refuses_overwrite(tmp_path) -> None:
    analysis, scope = _analysis_fixture()
    source = tmp_path / "input.json"
    source.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "hr_readout"
    paths = write_hr_readout_outputs(
        analysis, scope, _readout_config("nearest_tone"), output,
        input_artifacts=({"sample_id": "ms-1", "artifact_role": "feature_json", "path": source, "sha256": artifact_sha256(source)},),
        git_commit="test-commit", random_state=20260806,
        created_at_utc="2026-08-06T12:00:00+00:00",
    )

    required = {
        "calibration_reference_audit.csv", "tone_mapping.csv", "tone_coverage.csv",
        "hr_band_energy.csv", "hr_energy_fractions.csv", "hr_readout_qc.csv",
        "uncertainty_audit.csv", "feature_index.csv", "hr_readout_result.json",
        "hr_readout_manifest.json", "hr_readout_manifest.sha256",
        "hr_readout_diagnostic.png",
    }
    assert required <= set(paths)
    restored = load_hr_readout_bundle(output)
    assert restored.result.readout_id == analysis.result.readout_id
    assert restored.hr_band_energy_features[0].derivation is not None
    with pytest.raises(FileExistsError):
        write_hr_readout_outputs(
            analysis, scope, _readout_config("nearest_tone"), output,
            input_artifacts=(), git_commit="test", random_state=1,
        )


def test_hr_readout_loader_rejects_tampered_artifact(tmp_path) -> None:
    analysis, scope = _analysis_fixture()
    source = tmp_path / "input.json"
    source.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "hr_readout"
    write_hr_readout_outputs(
        analysis, scope, _readout_config("nearest_tone"), output,
        input_artifacts=({"path": source, "sha256": artifact_sha256(source)},),
        git_commit="test", random_state=1,
    )
    path = output / "tone_mapping.csv"
    path.write_text(path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact hash mismatch"):
        load_hr_readout_bundle(output)


def test_hr_feature_round_trip_loads_npz_with_pickle_disabled(tmp_path, monkeypatch) -> None:
    analysis, scope = _analysis_fixture()
    source = tmp_path / "input.json"
    source.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "hr_readout"
    write_hr_readout_outputs(
        analysis, scope, _readout_config("nearest_tone"), output,
        input_artifacts=({"path": source, "sha256": artifact_sha256(source)},),
        git_commit="test", random_state=1,
    )
    import acoustic_encoder.schemas as schema_module
    original = schema_module.np.load
    observed = []

    def audited_load(*args, **kwargs):
        observed.append(kwargs.get("allow_pickle"))
        return original(*args, **kwargs)

    monkeypatch.setattr(schema_module.np, "load", audited_load)
    restored = load_hr_readout_bundle(output)

    assert restored.hr_band_energy_features
    assert observed and all(value is False for value in observed)
