from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from acoustic_encoder.features import build_dense_feature_sets
from acoustic_encoder.quality_control import (
    MeasurementQCResult,
    QCCheckResult,
    QCScope,
    QCSourceStage,
    UnavailablePolicy,
)
from acoustic_encoder.research_gate import ResearchGateError, RunPurpose
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    FeatureKind,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    QCCheckStatus,
    QCStatus,
    Representation,
    SourceFormat,
    SpectrumData,
)
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET


def _preprocessing_config() -> dict:
    return {
        "schema_version": "1.1.0",
        "analysis_band_hz": [1000, 1040],
        "common_grid_step_hz": 10,
        "interpolation": "linear",
        "maximum_interpolation_gap_hz": 20,
        "minimum_valid_grid_fraction": 0.8,
        "normalization_band_hz": [1000, 1040],
        "minimum_normalization_points": 2,
        "minimum_zscore_std_db": 1.0e-9,
        "smoothing_domain": "db",
        "smoothing": {"method": "none"},
    }


def _dense_spectrum(
    frequency_hz: np.ndarray | None = None,
    magnitude_db: np.ndarray | None = None,
    valid_mask: np.ndarray | None = None,
    *,
    magnitude_quantity: str = "spl",
) -> SpectrumData:
    frequency = (
        np.arange(1000.0, 1040.0 + 10.0, 10.0)
        if frequency_hz is None
        else frequency_hz
    )
    magnitude = (
        np.array([70.0, 71.0, 72.0, 73.0, 74.0])
        if magnitude_db is None
        else magnitude_db
    )
    mask = np.ones(frequency.size, dtype=bool) if valid_mask is None else valid_mask
    meta = MeasurementMeta(
        sample_id="p3-dense-fixture",
        **SCHEMA_VERSION_QUARTET,
        device_version="V2",
        configuration="U4ENC",
        angle_deg=0.0,
        session_id="S01",
        repeat_type="CONT",
        repeat_id="R01",
        experiment_step="DEV_C2",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.MOCK_DENSE,
        source_path="synthetic-dense-spectrum.txt",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256="1" * 64,
        provenance_uri="software-validation-fixture",
        eligible_for_scientific_analysis=False,
    )
    return SpectrumData(
        frequency_hz=frequency,
        magnitude_db=magnitude,
        valid_mask=mask,
        representation=Representation.DENSE_SPECTRUM,
        phase_status=PhaseStatus.UNAVAILABLE,
        quality_metrics={},
        magnitude_quantity=magnitude_quantity,
        meta=meta,
    )


def _measurement_qc(spectrum: SpectrumData) -> MeasurementQCResult:
    return MeasurementQCResult(
        qc_schema_version="1.0.0",
        sample_id=spectrum.meta.sample_id,
        measurement_mode=spectrum.meta.measurement_mode,
        data_origin=spectrum.meta.data_origin,
        dataset_role=spectrum.meta.dataset_role,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        checks=(),
        unavailable_required_policy=UnavailablePolicy.WARNING,
        manual_review_reasons=spectrum.meta.manual_review_reasons,
        human_valid=spectrum.meta.valid,
        human_exclusion_reason=spectrum.meta.exclusion_reason,
        scientifically_eligible=spectrum.meta.eligible_for_scientific_analysis,
    )


def test_on_grid_spl_builds_three_dense_feature_sets() -> None:
    spectrum = _dense_spectrum()

    result = build_dense_feature_sets(
        spectrum,
        _measurement_qc(spectrum),
        _preprocessing_config(),
    )

    assert result.processing_status == "completed"
    assert set(result.feature_sets) == {
        FeatureKind.DENSE_RAW_SPL,
        FeatureKind.DENSE_DEMEANED_DB,
        FeatureKind.DENSE_ZSCORE,
    }
    raw = result.feature_sets[FeatureKind.DENSE_RAW_SPL]
    demeaned = result.feature_sets[FeatureKind.DENSE_DEMEANED_DB]
    zscore = result.feature_sets[FeatureKind.DENSE_ZSCORE]
    assert raw.feature_names == (
        "f_1000_hz",
        "f_1010_hz",
        "f_1020_hz",
        "f_1030_hz",
        "f_1040_hz",
    )
    np.testing.assert_array_equal(raw.values, spectrum.magnitude_db)
    np.testing.assert_allclose(demeaned.values, [-2, -1, 0, 1, 2])
    np.testing.assert_allclose(
        zscore.values,
        np.array([-2, -1, 0, 1, 2]) / np.sqrt(2),
    )
    assert raw.units == ("dB",) * 5
    assert demeaned.units == ("dB",) * 5
    assert zscore.units == ("dimensionless",) * 5
    assert raw.feature_names == demeaned.feature_names == zscore.feature_names
    assert raw.meta == spectrum.meta


def test_irregular_dense_grid_is_linearly_interpolated() -> None:
    spectrum = _dense_spectrum(
        frequency_hz=np.array([995.0, 1005.0, 1025.0, 1045.0]),
        magnitude_db=np.array([69.5, 70.5, 72.5, 74.5]),
    )

    result = build_dense_feature_sets(
        spectrum,
        _measurement_qc(spectrum),
        _preprocessing_config(),
    )

    raw = result.feature_sets[FeatureKind.DENSE_RAW_SPL]
    np.testing.assert_allclose(raw.values, [70, 71, 72, 73, 74])
    np.testing.assert_array_equal(raw.valid_mask, np.ones(5, dtype=bool))


def test_different_source_grids_produce_identical_dense_feature_schema() -> None:
    on_grid = _dense_spectrum()
    irregular = _dense_spectrum(
        frequency_hz=np.array([995.0, 1005.0, 1025.0, 1045.0]),
        magnitude_db=np.array([69.5, 70.5, 72.5, 74.5]),
    )

    first = build_dense_feature_sets(
        on_grid,
        _measurement_qc(on_grid),
        _preprocessing_config(),
    )
    second = build_dense_feature_sets(
        irregular,
        _measurement_qc(irregular),
        _preprocessing_config(),
    )

    assert first.feature_names == second.feature_names
    assert first.preprocessing_id == second.preprocessing_id
    assert {
        feature.feature_names for feature in first.feature_sets.values()
    } == {
        feature.feature_names for feature in second.feature_sets.values()
    }


def test_grid_points_outside_valid_source_range_are_not_extrapolated() -> None:
    spectrum = _dense_spectrum(
        frequency_hz=np.array([1010.0, 1020.0, 1030.0]),
        magnitude_db=np.array([71.0, 72.0, 73.0]),
    )
    config = _preprocessing_config()
    config["minimum_valid_grid_fraction"] = 0.6

    result = build_dense_feature_sets(
        spectrum,
        _measurement_qc(spectrum),
        config,
    )

    raw = result.feature_sets[FeatureKind.DENSE_RAW_SPL]
    np.testing.assert_array_equal(
        raw.valid_mask,
        np.array([False, True, True, True, False]),
    )
    assert np.isnan(raw.values[0])
    assert np.isnan(raw.values[-1])
    assert result.warnings == ("partial_grid_coverage",)


def test_valid_grid_fraction_below_configured_minimum_is_a_recorded_failure() -> None:
    spectrum = _dense_spectrum(
        frequency_hz=np.array([1010.0, 1020.0, 1030.0]),
        magnitude_db=np.array([71.0, 72.0, 73.0]),
    )

    result = build_dense_feature_sets(
        spectrum,
        _measurement_qc(spectrum),
        _preprocessing_config(),
    )

    assert result.processing_status == "failed"
    assert result.feature_sets == {}
    assert result.valid_grid_fraction == 0.6
    assert {failure.reason for failure in result.failures} == {
        "minimum_valid_grid_fraction_not_met"
    }
    assert {failure.feature_kind for failure in result.failures} == {
        FeatureKind.DENSE_RAW_SPL,
        FeatureKind.DENSE_DEMEANED_DB,
        FeatureKind.DENSE_ZSCORE,
    }


def test_invalid_source_point_is_neither_used_nor_interpolated_across() -> None:
    spectrum = _dense_spectrum(
        frequency_hz=np.array([1000.0, 1010.0, 1030.0, 1040.0]),
        magnitude_db=np.array([70.0, 999.0, 73.0, 74.0]),
        valid_mask=np.array([True, False, True, True]),
    )
    config = _preprocessing_config()
    config["minimum_valid_grid_fraction"] = 0.6

    result = build_dense_feature_sets(
        spectrum,
        _measurement_qc(spectrum),
        config,
    )

    raw = result.feature_sets[FeatureKind.DENSE_RAW_SPL]
    np.testing.assert_array_equal(
        raw.valid_mask,
        np.array([True, False, False, True, True]),
    )
    assert np.isnan(raw.values[1:3]).all()


def test_interpolation_gap_boundary_is_inclusive_and_larger_gap_is_invalid() -> None:
    spectrum = _dense_spectrum(
        frequency_hz=np.array([995.0, 1005.0, 1025.0, 1055.0]),
        magnitude_db=np.array([69.5, 70.5, 72.5, 75.5]),
    )
    config = _preprocessing_config()
    config["minimum_valid_grid_fraction"] = 0.6

    result = build_dense_feature_sets(
        spectrum,
        _measurement_qc(spectrum),
        config,
    )

    raw = result.feature_sets[FeatureKind.DENSE_RAW_SPL]
    np.testing.assert_array_equal(
        raw.valid_mask,
        np.array([True, True, True, False, False]),
    )
    np.testing.assert_allclose(raw.values[:3], [70.0, 71.0, 72.0])
    assert np.isnan(raw.values[3:]).all()


def test_transfer_ratio_is_not_mislabeled_as_raw_spl() -> None:
    spectrum = _dense_spectrum(magnitude_quantity="transfer_ratio")

    result = build_dense_feature_sets(
        spectrum,
        _measurement_qc(spectrum),
        _preprocessing_config(),
    )

    assert result.processing_status == "partial_failure"
    assert FeatureKind.DENSE_RAW_SPL not in result.feature_sets
    assert set(result.feature_sets) == {
        FeatureKind.DENSE_DEMEANED_DB,
        FeatureKind.DENSE_ZSCORE,
    }
    assert [(failure.feature_kind, failure.reason) for failure in result.failures] == [
        (
            FeatureKind.DENSE_RAW_SPL,
            "raw_spl_requires_spl_quantity",
        )
    ]
    assert result.magnitude_quantity == "transfer_ratio"


def test_constant_spectrum_records_zscore_failure_without_losing_raw_or_demeaned() -> None:
    spectrum = _dense_spectrum(magnitude_db=np.full(5, 72.0))

    result = build_dense_feature_sets(
        spectrum,
        _measurement_qc(spectrum),
        _preprocessing_config(),
    )

    assert result.processing_status == "partial_failure"
    assert set(result.feature_sets) == {
        FeatureKind.DENSE_RAW_SPL,
        FeatureKind.DENSE_DEMEANED_DB,
    }
    np.testing.assert_array_equal(
        result.feature_sets[FeatureKind.DENSE_DEMEANED_DB].values,
        np.zeros(5),
    )
    assert [(failure.feature_kind, failure.reason) for failure in result.failures] == [
        (FeatureKind.DENSE_ZSCORE, "zscore_standard_deviation_too_small")
    ]


def test_insufficient_normalization_points_preserve_raw_and_fail_normalized_kinds() -> None:
    spectrum = _dense_spectrum(
        valid_mask=np.array([True, False, True, True, True]),
    )
    config = _preprocessing_config()
    config["normalization_band_hz"] = [1000, 1010]

    result = build_dense_feature_sets(
        spectrum,
        _measurement_qc(spectrum),
        config,
    )

    assert result.processing_status == "partial_failure"
    assert set(result.feature_sets) == {FeatureKind.DENSE_RAW_SPL}
    assert {
        (failure.feature_kind, failure.reason) for failure in result.failures
    } == {
        (
            FeatureKind.DENSE_DEMEANED_DB,
            "minimum_normalization_points_not_met",
        ),
        (
            FeatureKind.DENSE_ZSCORE,
            "minimum_normalization_points_not_met",
        ),
    }


def test_smoothing_precedes_sample_local_normalization() -> None:
    spectrum = _dense_spectrum(magnitude_db=np.array([0.0, 0.0, 9.0, 0.0, 0.0]))
    config = _preprocessing_config()
    config["smoothing"] = {
        "method": "moving_average_linear_hz",
        "window_hz": 30,
        "boundary": "truncate",
        "minimum_kernel_coverage": 0.5,
    }

    result = build_dense_feature_sets(
        spectrum,
        _measurement_qc(spectrum),
        config,
    )

    raw = result.feature_sets[FeatureKind.DENSE_RAW_SPL]
    demeaned = result.feature_sets[FeatureKind.DENSE_DEMEANED_DB]
    zscore = result.feature_sets[FeatureKind.DENSE_ZSCORE]
    np.testing.assert_allclose(raw.values, [0.0, 3.0, 3.0, 3.0, 0.0])
    np.testing.assert_allclose(demeaned.values, raw.values - np.mean(raw.values))
    assert np.isclose(np.mean(zscore.values), 0.0)
    assert np.isclose(np.std(zscore.values), 1.0)
    np.testing.assert_array_equal(raw.valid_mask, demeaned.valid_mask)
    np.testing.assert_array_equal(raw.valid_mask, zscore.valid_mask)


def test_smoothing_coverage_failure_is_structured_without_feature_artifacts() -> None:
    spectrum = _dense_spectrum()
    config = _preprocessing_config()
    config["smoothing"] = {
        "method": "moving_average_linear_hz",
        "window_hz": 50,
        "boundary": "truncate",
        "minimum_kernel_coverage": 1.0,
    }

    result = build_dense_feature_sets(
        spectrum,
        _measurement_qc(spectrum),
        config,
    )

    assert result.processing_status == "failed"
    assert result.feature_sets == {}
    assert result.interpolated_valid_grid_fraction == 1.0
    assert result.valid_grid_fraction == 0.2
    assert result.smoothing_definition["method"] == "moving_average_linear_hz"
    assert {failure.reason for failure in result.failures} == {
        "minimum_valid_grid_fraction_not_met"
    }


def test_qc_exclude_and_human_invalid_are_preserved_without_deleting_features() -> None:
    spectrum = _dense_spectrum()
    meta = replace(
        spectrum.meta,
        valid=False,
        exclusion_reason="operator_rejected_fixture",
    )
    spectrum = replace(spectrum, meta=meta)
    qc = replace(
        _measurement_qc(spectrum),
        checks=(
            QCCheckResult(
                check_id="p2.fixture.exclude",
                scope=QCScope.MEASUREMENT,
                status=QCCheckStatus.EXCLUDE_CANDIDATE,
                source_stage=QCSourceStage.P2,
                source_module="test.features",
                reason="fixture_exclude_candidate",
            ),
        ),
    )

    result = build_dense_feature_sets(spectrum, qc, _preprocessing_config())

    assert len(result.feature_sets) == 3
    assert qc.aggregate_status is QCStatus.EXCLUDE_CANDIDATE
    assert qc.human_valid is False
    for feature in result.feature_sets.values():
        assert feature.source_qc_status is QCStatus.EXCLUDE_CANDIDATE
        assert feature.source_qc_exclude_candidate_reasons == (
            "fixture_exclude_candidate",
        )
        assert feature.source_qc_eligible_for_downstream is False
        assert feature.meta.valid is False
        assert feature.meta.exclusion_reason == "operator_rejected_fixture"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sample_id", "different-sample"),
        ("measurement_mode", MeasurementMode.SCHROEDER_MULTISINE),
        ("data_origin", DataOrigin.EXTERNAL_REFERENCE),
        ("dataset_role", DatasetRole.PARSER_FIXTURE),
        ("human_valid", False),
    ],
)
def test_mismatched_p2_result_is_rejected(field: str, value: object) -> None:
    spectrum = _dense_spectrum()
    qc = replace(_measurement_qc(spectrum), **{field: value})

    with pytest.raises(ValueError, match="MeasurementQCResult"):
        build_dense_feature_sets(spectrum, qc, _preprocessing_config())


def test_external_reference_cannot_enter_research_analysis_through_p3() -> None:
    spectrum = _dense_spectrum()
    spectrum = replace(
        spectrum,
        meta=replace(
            spectrum.meta,
            data_origin=DataOrigin.EXTERNAL_REFERENCE,
            dataset_role=DatasetRole.PARSER_FIXTURE,
            source_format=SourceFormat.REW_TXT,
            device_version=None,
            configuration=None,
            angle_deg=None,
            session_id=None,
            repeat_type=None,
            repeat_id=None,
            experiment_step=None,
        ),
    )
    qc = replace(
        _measurement_qc(spectrum),
        run_purpose=RunPurpose.RESEARCH_ANALYSIS,
    )

    with pytest.raises(ResearchGateError):
        build_dense_feature_sets(spectrum, qc, _preprocessing_config())


def test_warning_qc_is_preserved_without_deleting_features() -> None:
    spectrum = _dense_spectrum()
    qc = replace(
        _measurement_qc(spectrum),
        checks=(
            QCCheckResult(
                check_id="p2.fixture.warning",
                scope=QCScope.MEASUREMENT,
                status=QCCheckStatus.WARNING,
                source_stage=QCSourceStage.P2,
                source_module="test.features",
                reason="fixture_warning",
            ),
        ),
    )

    result = build_dense_feature_sets(spectrum, qc, _preprocessing_config())

    assert len(result.feature_sets) == 3
    for feature in result.feature_sets.values():
        assert feature.source_qc_status is QCStatus.WARNING
        assert feature.source_qc_warning_reasons == ("fixture_warning",)
