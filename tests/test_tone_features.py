from __future__ import annotations

from pathlib import Path
from dataclasses import replace

import numpy as np
import pytest

from acoustic_encoder.quality_control import MeasurementQCResult, UnavailablePolicy
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    FeatureKind,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    Representation,
    SourceFormat,
    SpectrumData,
)
from acoustic_encoder.tone_features import (
    ToneFeatureConstructionError,
    assert_matched_tone_schema,
    build_matched_tone_view,
    build_multisine_tone_feature_set,
    build_sweep_tone_feature_set,
    normalize_tone_values,
)
from acoustic_encoder.tone_sets import ToneDefinition, ToneSetDefinition
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET


def _tone_set(frequencies: tuple[float, ...]) -> ToneSetDefinition:
    tones = tuple(
        ToneDefinition(index, frequency, str(frequency), 100 + index, 1.0, 0.0)
        for index, frequency in enumerate(frequencies)
    )
    return ToneSetDefinition(
        tone_set_id="tone-set-p3c-test",
        sample_rate_hz=48000,
        period_samples=4800,
        tones=tones,
        tones_sha256="1" * 64,
        tone_set_sha256="2" * 64,
        manifest_sha256="3" * 64,
        manifest_path=Path("stimulus_manifest.json"),
        tones_path=Path("tones.csv"),
        verified_artifacts=True,
    )


def _sweep(
    *,
    frequency_hz: np.ndarray | None = None,
    magnitude_db: np.ndarray | None = None,
    valid_mask: np.ndarray | None = None,
) -> SpectrumData:
    frequency = (
        np.array([1000.0, 1010.0, 1020.0, 1030.0])
        if frequency_hz is None
        else frequency_hz
    )
    meta = MeasurementMeta(
        sample_id="p3c-sweep",
        **SCHEMA_VERSION_QUARTET,
        device_version="V2",
        configuration="U4ENC",
        angle_deg=0.0,
        session_id="S01",
        repeat_type="CONT",
        repeat_id="R01",
        experiment_step="DEV_C4",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.MOCK_DENSE,
        source_path="synthetic.txt",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256="4" * 64,
        provenance_uri="mock_manifest.json",
        eligible_for_scientific_analysis=False,
    )
    return SpectrumData(
        frequency_hz=frequency,
        magnitude_db=(
            np.array([10.0, 20.0, 30.0, 40.0])
            if magnitude_db is None
            else magnitude_db
        ),
        valid_mask=(
            np.ones(frequency.size, dtype=bool)
            if valid_mask is None
            else valid_mask
        ),
        representation=Representation.DENSE_SPECTRUM,
        phase_status=PhaseStatus.UNAVAILABLE,
        quality_metrics={},
        magnitude_quantity="spl",
        magnitude_reference="20uPa",
        meta=meta,
    )


def _qc(spectrum: SpectrumData) -> MeasurementQCResult:
    return MeasurementQCResult(
        qc_schema_version="1.0.0",
        sample_id=spectrum.meta.sample_id,
        measurement_mode=spectrum.meta.measurement_mode,
        data_origin=spectrum.meta.data_origin,
        dataset_role=spectrum.meta.dataset_role,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        checks=(),
        unavailable_required_policy=UnavailablePolicy.WARNING,
        manual_review_reasons=(),
        human_valid=True,
        human_exclusion_reason=None,
        scientifically_eligible=False,
    )


def _multisine(
    frequency_hz: np.ndarray,
    magnitude_db: np.ndarray,
    *,
    valid_mask: np.ndarray | None = None,
) -> SpectrumData:
    meta = MeasurementMeta(
        sample_id="p3c-multisine",
        **SCHEMA_VERSION_QUARTET,
        device_version="V2",
        configuration="U4ENC",
        angle_deg=0.0,
        session_id="S01",
        repeat_type="CONT",
        repeat_id="R01",
        experiment_step="DEV_C4",
        measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        stimulus_id="stimulus-p3c",
        stimulus_hash="5" * 64,
        tone_set_id="tone-set-p3c-test",
        sidecar_path="recording.json",
        audio_channel=0,
        source_format=SourceFormat.MOCK_AUDIO,
        source_path="recording.wav",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256="6" * 64,
        provenance_uri="mock_manifest.json",
        eligible_for_scientific_analysis=False,
    )
    quality = [
        {
            "frequency_hz": float(frequency),
            "missing_tone": False,
            "valid_tone": bool(valid),
            "reasons": [] if valid else ["fixture_invalid_tone"],
        }
        for frequency, valid in zip(
            frequency_hz,
            (
                np.ones(frequency_hz.size, dtype=bool)
                if valid_mask is None
                else valid_mask
            ),
            strict=True,
        )
    ]
    return SpectrumData(
        frequency_hz=frequency_hz,
        magnitude_db=magnitude_db,
        valid_mask=(
            np.ones(frequency_hz.size, dtype=bool)
            if valid_mask is None
            else valid_mask
        ),
        representation=Representation.SPARSE_TONES,
        phase_status=PhaseStatus.RELATIVE_UNRELIABLE,
        quality_metrics={
            "tone_set": {
                "tone_set_id": "tone-set-p3c-test",
                "tone_set_sha256": "2" * 64,
                "tones_sha256": "1" * 64,
                "verified_artifacts": True,
            },
            "tone_quality": quality,
        },
        magnitude_quantity="transfer_ratio",
        magnitude_reference="sha256:" + "5" * 64,
        meta=meta,
    )


def _dense_config() -> dict:
    return {
        "schema_version": "1.1.0",
        "analysis_band_hz": [1000, 1030],
        "common_grid_step_hz": 10,
        "interpolation": "linear",
        "maximum_interpolation_gap_hz": 10,
        "minimum_valid_grid_fraction": 0.5,
        "normalization_band_hz": [1000, 1030],
        "minimum_normalization_points": 2,
        "minimum_zscore_std_db": 1.0e-9,
        "smoothing_domain": "db",
        "smoothing": {"method": "none"},
    }


def _dense_config_for(low: float, high: float) -> dict:
    config = _dense_config()
    config["analysis_band_hz"] = [low, high]
    config["normalization_band_hz"] = [low, high]
    return config


def _matched_config(method: str = "none") -> dict:
    return {
        "schema_version": "1.0.0",
        "tone_ordering": "manifest_tone_index",
        "sweep_extraction": {"method": "single_point_linear"},
        "normalization": {
            "method": method,
            "minimum_valid_tones": 2,
            "minimum_std_db": 1.0e-9,
        },
        "matching": {"minimum_common_valid_tones": 2},
    }


def _narrowband_config(
    *,
    bandwidth_hz: float = 20.0,
    minimum_coverage: float = 1.0,
) -> dict:
    config = _matched_config()
    config["sweep_extraction"] = {
        "method": "narrowband_integration",
        "full_bandwidth_hz": bandwidth_hz,
        "integration_domain": "linear_power_ratio",
        "minimum_band_coverage": minimum_coverage,
        "overlap_policy": "reject",
    }
    return config


def test_single_point_uses_grid_nodes_and_linear_db_interpolation() -> None:
    spectrum = _sweep()
    tone_set = _tone_set((1000.0, 1015.0, 1030.0))

    result = build_sweep_tone_feature_set(
        spectrum,
        _qc(spectrum),
        _dense_config(),
        tone_set,
        _matched_config(),
    )

    feature = result.feature_set
    assert feature is not None
    assert feature.feature_kind is FeatureKind.TONE_PROJECTION_FROM_SWEEP
    np.testing.assert_allclose(feature.values, [10.0, 25.0, 40.0])
    assert feature.feature_names == tone_set.feature_names
    assert result.extraction_records[0].source_weights == (1.0,)
    assert result.extraction_records[1].source_frequency_hz == (1010.0, 1020.0)
    assert result.extraction_records[1].source_weights == (0.5, 0.5)


def test_single_point_does_not_cross_invalid_gap() -> None:
    spectrum = _sweep(valid_mask=np.array([True, True, False, True]))

    result = build_sweep_tone_feature_set(
        spectrum,
        _qc(spectrum),
        _dense_config(),
        _tone_set((1000.0, 1015.0, 1030.0)),
        _matched_config(),
    )

    assert result.feature_set is not None
    np.testing.assert_array_equal(result.feature_set.valid_mask, [True, False, True])
    assert np.isnan(result.feature_set.values[1])
    assert result.extraction_records[1].reason == "invalid_gap_crossing_forbidden"


def test_single_point_never_extrapolates() -> None:
    spectrum = _sweep()
    config = _matched_config()
    config["normalization"]["minimum_valid_tones"] = 1

    result = build_sweep_tone_feature_set(
        spectrum,
        _qc(spectrum),
        _dense_config(),
        _tone_set((990.0, 1040.0)),
        config,
    )

    assert result.feature_set is None
    assert [record.reason for record in result.extraction_records] == [
        "extrapolation_forbidden",
        "extrapolation_forbidden",
    ]


def test_narrowband_constant_response_is_unchanged() -> None:
    spectrum = _sweep(magnitude_db=np.full(4, 12.5))

    result = build_sweep_tone_feature_set(
        spectrum,
        _qc(spectrum),
        _dense_config(),
        _tone_set((1015.0,)),
        {
            **_narrowband_config(),
            "normalization": {
                "method": "none",
                "minimum_valid_tones": 1,
                "minimum_std_db": 1.0e-9,
            },
        },
    )

    assert result.feature_set is not None
    assert result.feature_set.values[0] == pytest.approx(12.5)
    assert result.extraction_records[0].coverage_fraction == pytest.approx(1.0)


def test_narrowband_integrates_piecewise_linear_power() -> None:
    spectrum = _sweep(
        frequency_hz=np.array([1000.0, 1010.0, 1020.0]),
        magnitude_db=np.array([0.0, 10.0, 0.0]),
    )

    result = build_sweep_tone_feature_set(
        spectrum,
        _qc(spectrum),
        _dense_config_for(1000, 1020),
        _tone_set((1010.0,)),
        {
            **_narrowband_config(),
            "normalization": {
                "method": "none",
                "minimum_valid_tones": 1,
                "minimum_std_db": 1.0e-9,
            },
        },
    )

    assert result.feature_set is not None
    assert result.feature_set.values[0] == pytest.approx(10 * np.log10(5.5))
    assert result.extraction_records[0].covered_bandwidth_hz == pytest.approx(20.0)


def test_narrowband_marks_insufficient_coverage_invalid() -> None:
    spectrum = _sweep(valid_mask=np.array([True, False, True, True]))

    result = build_sweep_tone_feature_set(
        spectrum,
        _qc(spectrum),
        _dense_config(),
        _tone_set((1005.0, 1025.0)),
        _narrowband_config(minimum_coverage=0.75),
    )

    assert result.feature_set is None
    assert result.extraction_records[0].reason == "minimum_band_coverage_not_met"
    assert result.extraction_records[0].coverage_fraction == pytest.approx(0.0)


def test_narrowband_rejects_overlapping_tone_bands() -> None:
    spectrum = _sweep()

    with pytest.raises(ToneFeatureConstructionError, match="overlap"):
        build_sweep_tone_feature_set(
            spectrum,
            _qc(spectrum),
            _dense_config(),
            _tone_set((1010.0, 1020.0)),
            _narrowband_config(bandwidth_hz=20.0),
        )


@pytest.mark.parametrize(
    ("method", "expected", "units"),
    [
        ("none", [1.0, 2.0, np.nan, 4.0], "dB"),
        ("subtract_mean_db", [-4 / 3, -1 / 3, np.nan, 5 / 3], "dB"),
        (
            "zscore_within_sample",
            np.array([-4 / 3, -1 / 3, np.nan, 5 / 3])
            / np.std([1.0, 2.0, 4.0]),
            "dimensionless",
        ),
    ],
)
def test_tone_normalization_uses_only_valid_tones(
    method: str,
    expected: list[float] | np.ndarray,
    units: str,
) -> None:
    result = normalize_tone_values(
        np.array([1.0, 2.0, 99.0, 4.0]),
        np.array([True, True, False, True]),
        {
            "method": method,
            "minimum_valid_tones": 2,
            "minimum_std_db": 1.0e-9,
        },
    )

    np.testing.assert_allclose(result.values, expected, equal_nan=True)
    np.testing.assert_array_equal(result.valid_mask, [True, True, False, True])
    assert result.units == units


def test_tone_normalization_rejects_too_few_valid_tones() -> None:
    with pytest.raises(ToneFeatureConstructionError, match="minimum_valid_tones"):
        normalize_tone_values(
            np.array([1.0, 2.0]),
            np.array([True, False]),
            {
                "method": "none",
                "minimum_valid_tones": 2,
                "minimum_std_db": 1.0e-9,
            },
        )


def test_tone_zscore_rejects_zero_standard_deviation() -> None:
    with pytest.raises(ToneFeatureConstructionError, match="standard deviation"):
        normalize_tone_values(
            np.array([1.0, 1.0, 1.0]),
            np.ones(3, dtype=bool),
            {
                "method": "zscore_within_sample",
                "minimum_valid_tones": 2,
                "minimum_std_db": 1.0e-9,
            },
        )


def test_multisine_direct_alignment_builds_matching_tone_schema() -> None:
    tone_set = _tone_set((1000.0, 1015.0, 1030.0))
    multisine = _multisine(
        np.array([1000.0, 1015.0, 1030.0]),
        np.array([10.0, 25.0, 40.0]),
    )
    sweep = _sweep()
    sweep_result = build_sweep_tone_feature_set(
        sweep,
        _qc(sweep),
        _dense_config(),
        tone_set,
        _matched_config(),
    )

    multisine_result = build_multisine_tone_feature_set(
        multisine,
        _qc(multisine),
        tone_set,
        _matched_config(),
    )

    feature = multisine_result.feature_set
    assert feature is not None
    assert feature.feature_kind is FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE
    np.testing.assert_allclose(feature.values, [10.0, 25.0, 40.0])
    assert feature.reliability_weights is None
    assert feature.source_phase_status == "relative_unreliable"
    assert feature.source_magnitude_quantity == "transfer_ratio"
    assert feature.tone_set_sha256 == tone_set.tone_set_sha256
    assert tuple(item.availability for item in feature.feature_quality) == (
        "available", "available", "available"
    )
    assert feature.feature_quality[0].details["missing_tone"] is False
    assert sweep_result.feature_set is not None
    assert_matched_tone_schema(sweep_result.feature_set, feature)


def test_multisine_missing_tone_keeps_authoritative_position_without_fill() -> None:
    tone_set = _tone_set((1000.0, 1015.0, 1030.0))
    multisine = _multisine(
        np.array([1000.0, 1030.0]),
        np.array([10.0, 40.0]),
    )

    result = build_multisine_tone_feature_set(
        multisine,
        _qc(multisine),
        tone_set,
        _matched_config(),
    )

    assert result.feature_set is not None
    np.testing.assert_array_equal(result.feature_set.valid_mask, [True, False, True])
    assert np.isnan(result.feature_set.values[1])
    assert result.extraction_records[1].reason == "tone_missing_from_sparse_spectrum"
    assert result.feature_set.feature_quality[1].availability == "missing"


def test_multisine_multiple_missing_tones_remain_nan() -> None:
    tone_set = _tone_set((1000.0, 1015.0, 1030.0))
    multisine = _multisine(np.array([1000.0]), np.array([10.0]))
    config = _matched_config()
    config["normalization"]["minimum_valid_tones"] = 1

    result = build_multisine_tone_feature_set(
        multisine,
        _qc(multisine),
        tone_set,
        config,
    )

    assert result.feature_set is not None
    np.testing.assert_array_equal(result.feature_set.valid_mask, [True, False, False])
    assert np.all(np.isnan(result.feature_set.values[1:]))


def test_multisine_rejects_frequency_not_in_authoritative_tone_set() -> None:
    multisine = _multisine(
        np.array([1000.0, 1014.0, 1030.0]),
        np.array([10.0, 25.0, 40.0]),
    )

    with pytest.raises(ToneFeatureConstructionError, match="not in authoritative"):
        build_multisine_tone_feature_set(
            multisine,
            _qc(multisine),
            _tone_set((1000.0, 1015.0, 1030.0)),
            _matched_config(),
        )


def test_common_valid_mask_is_non_destructive_and_retains_all_counts() -> None:
    tone_set = _tone_set((1000.0, 1015.0, 1030.0))
    sweep = _sweep(valid_mask=np.array([True, True, False, True]))
    sweep_result = build_sweep_tone_feature_set(
        sweep,
        _qc(sweep),
        _dense_config(),
        tone_set,
        _matched_config(),
    )
    multisine = _multisine(
        np.array([1000.0, 1030.0]),
        np.array([10.0, 40.0]),
    )
    multisine_result = build_multisine_tone_feature_set(
        multisine,
        _qc(multisine),
        tone_set,
        _matched_config(),
    )

    view = build_matched_tone_view(
        sweep_result,
        multisine_result,
        _matched_config(),
    )

    np.testing.assert_array_equal(view.common_valid_mask, [True, False, True])
    assert view.sweep_invalid_count == 1
    assert view.multisine_missing_count == 1
    assert view.common_valid_count == 2
    assert view.processing_status == "completed"
    np.testing.assert_array_equal(
        sweep_result.feature_set.valid_mask,  # type: ignore[union-attr]
        [True, False, True],
    )


def test_reference_mismatch_never_claims_absolute_comparability() -> None:
    tone_set = _tone_set((1000.0, 1015.0, 1030.0))
    sweep = _sweep()
    sweep_result = build_sweep_tone_feature_set(
        sweep,
        _qc(sweep),
        _dense_config(),
        tone_set,
        _matched_config(),
    )
    multisine = _multisine(
        np.array([1000.0, 1015.0, 1030.0]),
        np.array([10.0, 25.0, 40.0]),
    )
    multisine_result = build_multisine_tone_feature_set(
        multisine,
        _qc(multisine),
        tone_set,
        _matched_config(),
    )

    view = build_matched_tone_view(
        sweep_result,
        multisine_result,
        _matched_config(),
    )

    assert view.source_reference_status == "quantity_mismatch"
    assert view.comparison_status == "independent_mode_only"
    assert view.cross_mode_absolute_comparable is False


def test_common_calibration_allows_absolute_comparison_only_for_same_quantity() -> None:
    tone_set = _tone_set((1000.0, 1015.0, 1030.0))
    config = _matched_config()
    sweep = _sweep()
    sweep_result = build_sweep_tone_feature_set(
        sweep,
        _qc(sweep),
        _dense_config(),
        tone_set,
        config,
    )
    multisine = _multisine(
        np.array([1000.0, 1015.0, 1030.0]),
        np.array([10.0, 25.0, 40.0]),
    )
    multisine_result = build_multisine_tone_feature_set(
        multisine,
        _qc(multisine),
        tone_set,
        config,
    )
    assert sweep_result.feature_set is not None
    assert multisine_result.feature_set is not None
    sweep_feature = replace(
        sweep_result.feature_set,
        calibration_id="cal-common-v1",
        source_magnitude_reference="reference-a",
    )
    multisine_feature = replace(
        multisine_result.feature_set,
        calibration_id="cal-common-v1",
        source_magnitude_quantity="spl",
        source_magnitude_reference="reference-b",
    )
    sweep_result = replace(sweep_result, feature_set=sweep_feature)
    multisine_result = replace(multisine_result, feature_set=multisine_feature)

    view = build_matched_tone_view(sweep_result, multisine_result, config)

    assert view.source_reference_status == "shared_calibration"
    assert view.comparison_status == "absolute_comparable"
    assert view.cross_mode_absolute_comparable is True


def test_matched_schema_rejects_mismatch_without_reindexing() -> None:
    tone_set = _tone_set((1000.0, 1015.0, 1030.0))
    sweep = _sweep()
    sweep_result = build_sweep_tone_feature_set(
        sweep, _qc(sweep), _dense_config(), tone_set, _matched_config()
    )
    multisine = _multisine(
        np.array([1000.0, 1015.0, 1030.0]), np.array([10.0, 25.0, 40.0])
    )
    multisine_result = build_multisine_tone_feature_set(
        multisine, _qc(multisine), tone_set, _matched_config()
    )
    assert sweep_result.feature_set is not None
    assert multisine_result.feature_set is not None
    mismatched = replace(
        multisine_result.feature_set,
        tone_schema_id="sha256:" + "f" * 64,
    )

    with pytest.raises(ToneFeatureConstructionError, match="tone_schema_id"):
        assert_matched_tone_schema(sweep_result.feature_set, mismatched)


def test_common_valid_minimum_is_an_explicit_pair_failure() -> None:
    tone_set = _tone_set((1000.0, 1015.0, 1030.0))
    config = _matched_config()
    config["matching"]["minimum_common_valid_tones"] = 3
    sweep = _sweep(valid_mask=np.array([True, True, False, True]))
    sweep_result = build_sweep_tone_feature_set(
        sweep, _qc(sweep), _dense_config(), tone_set, config
    )
    multisine = _multisine(
        np.array([1000.0, 1030.0]), np.array([10.0, 40.0])
    )
    multisine_result = build_multisine_tone_feature_set(
        multisine, _qc(multisine), tone_set, config
    )

    view = build_matched_tone_view(sweep_result, multisine_result, config)

    assert view.processing_status == "failed"
    assert "minimum_common_valid_tones" in (view.failure_reason or "")


def test_tone_preprocessing_id_is_independent_of_mapping_order() -> None:
    tone_set = _tone_set((1000.0, 1015.0, 1030.0))
    spectrum = _sweep()
    config = _matched_config()
    reordered = dict(reversed(tuple(config.items())))

    first = build_sweep_tone_feature_set(
        spectrum, _qc(spectrum), _dense_config(), tone_set, config
    )
    second = build_sweep_tone_feature_set(
        spectrum, _qc(spectrum), _dense_config(), tone_set, reordered
    )

    assert first.preprocessing_id == second.preprocessing_id
    assert first.tone_schema_id == second.tone_schema_id
