from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from acoustic_encoder.dataset_quality_control import feature_set_content_sha256
from acoustic_encoder.cross_mode_bridge import (
    CalibrationStatus, CrossModeCalibrationModel, ToneCalibrationFit,
)
from acoustic_encoder.direction_models import fit_frozen_direction_model
from acoustic_encoder.offline_readout import (
    FrozenReadoutPackage,
    OfflineReadoutError,
    ReadoutInputReference,
    run_offline_readout,
)
from acoustic_encoder.quality_control import MeasurementQCResult, UnavailablePolicy
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import (
    DataOrigin, DatasetRole, MeasurementMeta, MeasurementMode, PhaseStatus,
    Representation, SourceFormat, SpectrumData,
)
from acoustic_encoder.tone_features import build_multisine_tone_feature_set
from acoustic_encoder.tone_sets import ToneDefinition, ToneSetDefinition
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _tone_set() -> ToneSetDefinition:
    frequencies = (1000.0, 1100.0, 1200.0)
    return ToneSetDefinition(
        "readout-tones-v1", 48000, 4800,
        tuple(ToneDefinition(i, f, str(int(f)), 100 + i * 10, 1.0, 0.0) for i, f in enumerate(frequencies)),
        "1" * 64, "2" * 64, "3" * 64,
        Path("stimulus_manifest.json"), Path("tones.csv"), True,
    )


def _qc(sample_id: str = "readout-input") -> MeasurementQCResult:
    return MeasurementQCResult(
        "1.0.0", sample_id, MeasurementMode.SCHROEDER_MULTISINE,
        DataOrigin.SIMULATED, DatasetRole.SOFTWARE_VALIDATION,
        RunPurpose.SOFTWARE_VALIDATION, (), UnavailablePolicy.WARNING,
        (), True, None, False,
    )


def _spectrum(*, mask=(True, True, True), stimulus_hash="4" * 64) -> SpectrumData:
    tone_set = _tone_set()
    meta = MeasurementMeta(
        sample_id="readout-input", **SCHEMA_VERSION_QUARTET,
        device_version="V2", configuration="U4ENC", angle_deg=90.0,
        session_id="S01", repeat_type="CONT", repeat_id="R01",
        experiment_step="DEV_C15", measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        stimulus_id="readout-stimulus-v1", stimulus_hash=stimulus_hash,
        tone_set_id=tone_set.tone_set_id, sidecar_path="input.json", audio_channel=0,
        source_format=SourceFormat.MOCK_AUDIO, source_path="input.wav",
        data_origin=DataOrigin.SIMULATED, dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256="5" * 64, provenance_uri="mock_manifest.json",
        eligible_for_scientific_analysis=False,
    )
    quality = [
        {"frequency_hz": f, "missing_tone": not valid, "valid_tone": valid,
         "snr_db": 50.0 if valid else None, "snr_status": "valid" if valid else "unavailable",
         "qc_reasons": [] if valid else ["missing_tone"]}
        for f, valid in zip(tone_set.frequency_hz, mask, strict=True)
    ]
    return SpectrumData(
        tone_set.frequency_hz, np.asarray([-2.0, 4.0, -1.0]),
        np.asarray(mask), Representation.SPARSE_TONES, PhaseStatus.RELATIVE_UNRELIABLE,
        {
            "tone_set": {"tone_set_id": tone_set.tone_set_id, "tone_set_sha256": tone_set.tone_set_sha256,
                         "tones_sha256": tone_set.tones_sha256, "verified_artifacts": True},
            "tone_quality": quality,
            "synchronization_method": "preamble_cross_correlation",
            "clock_drift": {"final_decision": "valid", "correction_applied": False},
            "clipping": {"status": "valid", "clipped_sample_count": 0},
            "period_samples": 4800, "stable_period_count": 8, "discarded_period_count": 2,
            "p8_qc": {"aggregate_status": "valid"},
        },
        meta, None, "transfer_ratio", _sha("4"),
    )


def _matched_config() -> dict:
    return {
        "schema_version": "1.0.0", "tone_ordering": "manifest_tone_index",
        "sweep_extraction": {"method": "single_point_linear"},
        "normalization": {"method": "subtract_mean_db", "minimum_valid_tones": 3, "minimum_std_db": 1e-9},
        "matching": {"minimum_common_valid_tones": 3},
    }


def _package_and_model():
    tone_set = _tone_set()
    spectra = [
        np.asarray([-3.0, 1.0, 2.0]), np.asarray([-2.8, 1.2, 1.6]),
        np.asarray([-2.0, 4.0, -1.0]), np.asarray([-1.8, 3.8, -1.1]),
        np.asarray([2.0, -1.0, -1.0]), np.asarray([1.8, -0.8, -1.0]),
    ]
    labels = np.asarray([0.0, 0.0, 90.0, 90.0, 180.0, 180.0])
    # P3-C normalization is frozen and applied to training exactly as to readout.
    x = np.vstack([row - np.mean(row) for row in spectra])
    probe = build_multisine_tone_feature_set(_spectrum(), _qc(), tone_set, _matched_config()).feature_set
    assert probe is not None
    model = fit_frozen_direction_model(
        model_id="nearest_centroid", x_train=x, y_train=labels,
        direction_order=(0.0, 90.0, 180.0), feature_names=tone_set.feature_names,
        units=("dB",) * 3, training_sample_ids=tuple(f"train-{i}" for i in range(6)),
        training_roles=("development",) * 6,
        training_feature_sha256s=tuple(_sha(format(i + 1, "x")) for i in range(6)),
        feature_kind=probe.feature_kind.value, preprocessing_id=probe.preprocessing_id,
        tone_set_id=tone_set.tone_set_id, tone_set_sha256=_sha("2"),
        normalization_method="subtract_mean_db", magnitude_quantity="transfer_ratio",
        magnitude_reference=_sha("4"), model_domain="multisine",
        authority_hashes={"p2b": _sha("6"), "p4b": _sha("7"), "p5": _sha("8"),
                          "p9a": _sha("9"), "p9b": _sha("a")},
        sealed_final_test_sample_ids=("sealed-final",), sealed_final_test_sha256=_sha("b"),
        random_state=20260806,
    )
    package = FrozenReadoutPackage.create(
        package_id="DEV-C15-validation-package", created_utc="2026-08-06T12:00:00Z",
        stimulus_id="readout-stimulus-v1", stimulus_waveform_sha256=_sha("4"),
        stimulus_manifest_file_sha256=_sha("c"), stimulus_manifest_semantic_sha256=_sha("d"),
        tone_set=tone_set, model=model, matched_tone_config=_matched_config(),
        qc_policy={"required_tone_coverage": 1.0, "phase_policy": "magnitude_only_warning",
                   "p8_exclude_candidate_action": "invalid"},
        authority_hashes=model.authority_hashes,
        pipeline_version="2.0.0-dev.21", config_schema_version="2.20.0",
        measurement_schema_version="2.4.0", feature_schema_version="2.3.0",
        stable_period_count=8, discard_initial_period_count=2,
    )
    return package, model


def _input_reference() -> ReadoutInputReference:
    return ReadoutInputReference(
        "1.0.0", "readout-input", _sha("e"), _sha("f"), _sha("1"),
        _sha("2"), _sha("3"), _sha("4"),
    )


def test_clean_single_readout_returns_top_two_margin_and_phase_warning() -> None:
    package, model = _package_and_model()
    result = run_offline_readout(
        _spectrum(), _qc(), _tone_set(), _matched_config(), package, model,
        _input_reference(), calibration_model=None,
    )

    assert result.processing_status == "completed_with_warnings"
    assert result.prediction.available is True
    assert result.prediction.predicted_direction_deg == 90.0
    assert result.prediction.second_direction_deg in {0.0, 180.0}
    assert result.prediction.margin == pytest.approx(
        result.prediction.second_score - result.prediction.score
    )
    assert result.prediction.score_kind == "euclidean_distance"
    assert result.prediction.confidence_status == "descriptive_margin_only"
    assert result.qc_audit.phase_used is False
    assert result.qc_audit.status == "warning"
    assert result.scientifically_eligible is False
    assert result.deployment_eligible is False
    assert result.final_test_read is False


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("stimulus", "stimulus"), ("tone_set", "tone-set"),
        ("preprocessing", "preprocessing"), ("model", "model"),
    ],
)
def test_authority_mismatch_blocks_prediction(mutation: str, reason: str) -> None:
    package, model = _package_and_model()
    spectrum = _spectrum()
    matched = _matched_config()
    if mutation == "stimulus":
        spectrum = _spectrum(stimulus_hash="0" * 64)
    elif mutation == "tone_set":
        package = replace(package, tone_set_sha256=_sha("0"))
    elif mutation == "preprocessing":
        matched = {**matched, "normalization": {**matched["normalization"], "minimum_valid_tones": 2}}
    else:
        package = replace(package, model_semantic_sha256=_sha("0"))

    result = run_offline_readout(
        spectrum, _qc(), _tone_set(), matched, package, model,
        _input_reference(), calibration_model=None,
    )

    assert result.processing_status == "blocked"
    assert result.prediction.available is False
    assert any(reason in item for item in result.failure_reasons)


def test_missing_required_tone_is_unavailable_without_input_mutation() -> None:
    package, model = _package_and_model()
    spectrum = _spectrum(mask=(True, False, True))
    original_values = spectrum.magnitude_db.copy()
    original_mask = spectrum.valid_mask.copy()

    result = run_offline_readout(
        spectrum, _qc(), _tone_set(), _matched_config(), package, model,
        _input_reference(), calibration_model=None,
    )

    assert result.processing_status == "unavailable"
    assert result.prediction.available is False
    assert "required_tone_coverage" in result.prediction.unavailable_reason
    np.testing.assert_array_equal(spectrum.magnitude_db, original_values)
    np.testing.assert_array_equal(spectrum.valid_mask, original_mask)


def test_package_round_trip_detects_tamper_and_stays_software_validation_only() -> None:
    package, _ = _package_and_model()
    restored = FrozenReadoutPackage.from_dict(package.to_dict())
    assert restored.semantic_sha256 == package.semantic_sha256
    assert restored.lifecycle == "software_validation_only"
    assert restored.canonical_analysis is False
    payload = package.to_dict()
    payload["stimulus_waveform_sha256"] = _sha("0")
    with pytest.raises(OfflineReadoutError, match="semantic hash"):
        FrozenReadoutPackage.from_dict(payload)


def test_calibration_is_not_silently_skipped_when_model_domain_requires_it() -> None:
    package, model = _package_and_model()
    model_payload = model.to_dict()
    model_payload.pop("model_semantic_sha256")
    model_payload["model_domain"] = "sweep_projection"
    sweep_model = type(model).from_dict(model_payload)
    package = replace(package, model_semantic_sha256=sweep_model.semantic_sha256,
                      model_domain="sweep_projection", calibration_required=True)

    result = run_offline_readout(
        _spectrum(), _qc(), _tone_set(), _matched_config(), package, sweep_model,
        _input_reference(), calibration_model=None,
    )

    assert result.processing_status == "blocked"
    assert "calibration_required" in result.failure_reasons


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("synchronization_method", "unknown", "synchronization_invalid"),
        ("clock_drift", {"final_decision": "exclude_candidate"}, "clock_drift_invalid"),
        ("clipping", {"status": "exclude_candidate", "clipped_sample_count": 9}, "clipping_invalid"),
    ],
)
def test_frozen_qc_policy_propagates_sync_drift_and_clipping(field, value, reason) -> None:
    package, model = _package_and_model()
    spectrum = _spectrum()
    quality = dict(spectrum.quality_metrics)
    quality[field] = value
    spectrum = replace(spectrum, quality_metrics=quality)

    result = run_offline_readout(
        spectrum, _qc(), _tone_set(), _matched_config(), package, model,
        _input_reference(), calibration_model=None,
    )

    assert result.processing_status == "invalid"
    assert result.prediction.available is False
    assert reason in result.failure_reasons


def _identity_calibration(outer_fold_id: str = "frozen_readout") -> CrossModeCalibrationModel:
    package, _ = _package_and_model()
    fits = tuple(
        ToneCalibrationFit(
            "1.0.0", tone_id, frequency, "identity", CalibrationStatus.VALID,
            1.0, 0.0, ("cal-train",), 1, 1.0, 0.0, 0.0,
            "descriptive_only", (),
        )
        for tone_id, frequency in zip(package.ordered_tone_ids, package.ordered_frequencies_hz, strict=True)
    )
    return CrossModeCalibrationModel(
        "1.0.0", _sha("1"), outer_fold_id, "identity",
        "multisine_db_to_sweep_projection_db", package.ordered_tone_ids,
        package.ordered_frequencies_hz, fits, ("cal-train",), _sha("2"), (), (),
        _sha("3"), _sha("4"), _sha("5"), _sha("6"), _sha("7"), _sha("8"),
        _sha("9"), _sha("a"), "transfer_ratio", "transfer_ratio", "dB",
        _sha("4"), _sha("4"), "subtract_mean_db", "software_validation_only",
        "not_approved", False, False, False,
    )


def test_legal_frozen_calibration_applies_but_cv_fold_and_hash_tamper_block() -> None:
    package, model = _package_and_model()
    model_payload = model.to_dict()
    model_payload.pop("model_semantic_sha256")
    model_payload["model_domain"] = "sweep_projection"
    sweep_model = type(model).from_dict(model_payload)
    calibration = _identity_calibration()
    package = replace(
        package, model_domain="sweep_projection", model_semantic_sha256=sweep_model.semantic_sha256,
        calibration_required=True, calibration_model_semantic_sha256=calibration.sha256,
        calibration_mapping_direction="multisine_db_to_sweep_projection_db",
    )

    legal = run_offline_readout(
        _spectrum(), _qc(), _tone_set(), _matched_config(), package, sweep_model,
        _input_reference(), calibration_model=calibration,
    )
    assert legal.prediction.available is True
    assert legal.calibration_audit.applied is True
    assert legal.prediction.predicted_direction_deg == 90.0

    fold_model = replace(calibration, outer_fold_id="outer-S1")
    fold_package = replace(package, calibration_model_semantic_sha256=fold_model.sha256)
    rejected_fold = run_offline_readout(
        _spectrum(), _qc(), _tone_set(), _matched_config(), fold_package, sweep_model,
        _input_reference(), calibration_model=fold_model,
    )
    assert "cv_fold_calibration_forbidden" in rejected_fold.failure_reasons

    tampered_package = replace(package, calibration_model_semantic_sha256=_sha("0"))
    rejected_hash = run_offline_readout(
        _spectrum(), _qc(), _tone_set(), _matched_config(), tampered_package, sweep_model,
        _input_reference(), calibration_model=calibration,
    )
    assert "calibration_hash_mismatch" in rejected_hash.failure_reasons


@pytest.mark.parametrize("mutation", ["tone_order", "mapping"])
def test_calibration_tone_and_mapping_contracts_fail_closed(mutation: str) -> None:
    package, model = _package_and_model()
    model_payload = model.to_dict()
    model_payload.pop("model_semantic_sha256")
    model_payload["model_domain"] = "sweep_projection"
    sweep_model = type(model).from_dict(model_payload)
    calibration = _identity_calibration()
    if mutation == "tone_order":
        calibration = replace(calibration, ordered_tone_ids=tuple(reversed(calibration.ordered_tone_ids)))
    else:
        calibration = replace(calibration, mapping_direction="sweep_projection_db_to_multisine_db")
    package = replace(
        package, model_domain="sweep_projection", model_semantic_sha256=sweep_model.semantic_sha256,
        calibration_required=True, calibration_model_semantic_sha256=calibration.sha256,
        calibration_mapping_direction="multisine_db_to_sweep_projection_db",
    )

    result = run_offline_readout(
        _spectrum(), _qc(), _tone_set(), _matched_config(), package, sweep_model,
        _input_reference(), calibration_model=calibration,
    )

    assert result.processing_status == "blocked"
    assert any("calibration" in reason for reason in result.failure_reasons)
