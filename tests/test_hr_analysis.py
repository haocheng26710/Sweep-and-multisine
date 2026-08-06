from __future__ import annotations

import hashlib
from dataclasses import replace

import numpy as np
import pytest

from acoustic_encoder.dataset_quality_control import (
    CohortRole,
    DatasetInputAuditRecord,
    DatasetQCReference,
    DatasetQCResult,
    dataset_qc_sha256,
    feature_contract_sha256,
    feature_set_content_sha256,
)
from acoustic_encoder.hr_analysis import (
    HR_CALIBRATION_SCOPE_SCHEMA_VERSION,
    ApprovalRecord,
    FinalTestSeal,
    HRCalibrationGroupSpec,
    HRCalibrationScope,
    HRCalibrationScopeMember,
    HRInputError,
    ResonatorSearchSpec,
    analyze_sweep_hr_calibration,
)
from acoustic_encoder.quality_control import MeasurementQCResult, UnavailablePolicy, measurement_qc_sha256
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    FeatureKind,
    FeatureSet,
    MeasurementMeta,
    MeasurementMode,
    Representation,
    SourceFormat,
)
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET


def _feature(
    sample_id: str = "hr-cont-01",
    *,
    peak_hz: float = 1500.0,
    repeat_type: str = "CONT",
    session_id: str = "S01",
) -> FeatureSet:
    frequency = np.arange(1200.0, 1800.0 + 1.0, 1.0)
    q = 15.0
    linear_power = 1.0 + 100.0 / (1.0 + (2.0 * q * (frequency - peak_hz) / peak_hz) ** 2)
    values = 10.0 * np.log10(linear_power)
    qc = MeasurementQCResult(
        qc_schema_version="1.0.0",
        sample_id=sample_id,
        measurement_mode=MeasurementMode.REW_SWEEP,
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        checks=(),
        unavailable_required_policy=UnavailablePolicy.PRESERVE,
        manual_review_reasons=(),
        human_valid=True,
        human_exclusion_reason=None,
        scientifically_eligible=False,
    )
    digest = hashlib.sha256(sample_id.encode()).hexdigest()
    meta = MeasurementMeta(
        sample_id=sample_id,
        **SCHEMA_VERSION_QUARTET,
        device_version="V2.5",
        configuration="HR-SIM",
        angle_deg=0.0,
        session_id=session_id,
        repeat_type=repeat_type,
        repeat_id=sample_id,
        experiment_step="DEV_C10_P6A_TEST",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.MOCK_DENSE,
        source_path=f"mock://misleading-target-1700/{sample_id}",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256=digest,
        provenance_uri="mock://DEV-C10-P6A",
        eligible_for_scientific_analysis=False,
        acquisition_block_id="B01",
    )
    return FeatureSet(
        sample_id=sample_id,
        feature_schema_version=SCHEMA_VERSION_QUARTET["feature_schema_version"],
        feature_kind=FeatureKind.DENSE_RAW_SPL,
        feature_names=tuple(f"f_{value:g}_hz" for value in frequency),
        values=values,
        valid_mask=np.ones(values.size, dtype=bool),
        units=("dB",) * values.size,
        source_measurement_mode=MeasurementMode.REW_SWEEP,
        source_representation=Representation.DENSE_SPECTRUM,
        preprocessing_id="sha256:" + "1" * 64,
        meta=meta,
        normalization_method=None,
        source_magnitude_quantity="spl",
        source_qc_status=qc.aggregate_status,
        source_qc_sha256=measurement_qc_sha256(qc),
        source_qc_eligible_for_downstream=True,
    )


def _p2b(scope_id: str, features: tuple[FeatureSet, ...]) -> tuple[DatasetQCReference, DatasetQCResult]:
    result = DatasetQCResult(
        schema_version="1.0.0",
        analysis_scope_id=scope_id,
        scope_sha256="sha256:" + "2" * 64,
        config_sha256="sha256:" + "3" * 64,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        scoped_sample_ids=tuple(item.sample_id for item in features),
        condition_results=(),
        input_audit=tuple(
            DatasetInputAuditRecord(
                item.sample_id,
                CohortRole.DEVELOPMENT,
                feature_contract_sha256(item),
                feature_set_content_sha256(item),
                item.source_qc_sha256,
                item.meta.source_sha256,
                "explicit HR calibration fixture",
            )
            for item in features
        ),
    )
    return DatasetQCReference(scope_id, dataset_qc_sha256(result)), result


def _scope(feature: FeatureSet, reference: DatasetQCReference) -> HRCalibrationScope:
    resonator = ResonatorSearchSpec(
        module_id="hr-sim-module",
        resonator_id="R1",
        design_target_hz=1700.0,
        search_min_hz=1400.0,
        search_max_hz=1600.0,
        boundary="closed",
        minimum_prominence_db=3.0,
        minimum_peak_distance_hz=20.0,
        minimum_valid_points=5,
        peak_selection_rule="prominence_then_magnitude_then_lowest_frequency",
        bandwidth_drop_db=3.010299956639812,
        integration_method="measured_3db_band",
        integration_half_width_hz=None,
        minimum_integration_coverage=1.0,
    )
    member = HRCalibrationScopeMember.from_feature_set(
        feature,
        artifact_id="feature-hr-cont-01",
        feature_base_path="features/hr-cont-01",
        feature_npz_sha256="4" * 64,
        feature_json_sha256="5" * 64,
        configuration_id="HR-SIM",
        direction_id="A000",
        calibration_group_id="G1",
        energy_fraction_group_id="hr-cont-01",
        module_ids=("hr-sim-module",),
        resonator_ids=("R1",),
        cohort_role="development",
        scope_role="calibration",
        selection_reason="explicit simulated HR validation",
    )
    group = HRCalibrationGroupSpec(
        calibration_group_id="G1",
        ordered_sample_ids=(feature.sample_id,),
        configuration_id="HR-SIM",
        direction_ids=("A000",),
        session_ids=("S01",),
        repeat_types=("CONT",),
        pooling_reason="single explicit validation group",
    )
    return HRCalibrationScope(
        schema_version=HR_CALIBRATION_SCOPE_SCHEMA_VERSION,
        hr_calibration_scope_id="DEV-C10-scope",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        members=(member,),
        groups=(group,),
        resonators=(resonator,),
        p2b_reference=reference,
        preprocessing_id=feature.preprocessing_id,
        random_state=20260806,
        final_test_seal=FinalTestSeal(True, (), "sha256:" + "6" * 64),
    )


def _scope_many(features: tuple[FeatureSet, ...], reference: DatasetQCReference) -> HRCalibrationScope:
    template = _scope(features[0], reference)
    members = tuple(
        HRCalibrationScopeMember.from_feature_set(
            feature,
            artifact_id=f"feature-{feature.sample_id}",
            feature_base_path=f"features/{feature.sample_id}",
            feature_npz_sha256=hashlib.sha256((feature.sample_id + "npz").encode()).hexdigest(),
            feature_json_sha256=hashlib.sha256((feature.sample_id + "json").encode()).hexdigest(),
            configuration_id="HR-SIM",
            direction_id="A000",
            calibration_group_id="G1",
            energy_fraction_group_id=feature.sample_id,
            module_ids=("hr-sim-module",),
            resonator_ids=("R1",),
            cohort_role="development",
            scope_role="calibration",
            selection_reason="explicit simulated HR validation",
        )
        for feature in features
    )
    group = HRCalibrationGroupSpec(
        calibration_group_id="G1",
        ordered_sample_ids=tuple(item.sample_id for item in features),
        configuration_id="HR-SIM",
        direction_ids=("A000",),
        session_ids=tuple(sorted({item.meta.session_id for item in features})),
        repeat_types=tuple(sorted({item.meta.repeat_type for item in features})),
        pooling_reason="explicit repeated-measurement validation group",
    )
    return replace(template, members=members, groups=(group,))


def _resonator_config(spec: ResonatorSearchSpec) -> dict[str, object]:
    return {
        "module_id": spec.module_id,
        "resonator_id": spec.resonator_id,
        "design_target_hz": spec.design_target_hz,
        "search_min_hz": spec.search_min_hz,
        "search_max_hz": spec.search_max_hz,
        "boundary": spec.boundary,
        "minimum_prominence_db": spec.minimum_prominence_db,
        "minimum_peak_distance_hz": spec.minimum_peak_distance_hz,
        "minimum_valid_points": spec.minimum_valid_points,
        "peak_selection_rule": spec.peak_selection_rule,
        "bandwidth_drop_db": spec.bandwidth_drop_db,
        "integration": {
            "method": spec.integration_method,
            **({"half_width_hz": spec.integration_half_width_hz} if spec.integration_half_width_hz is not None else {}),
            "minimum_coverage_fraction": spec.minimum_integration_coverage,
        },
    }


def _config(resonators: tuple[ResonatorSearchSpec, ...] | None = None) -> dict[str, object]:
    if resonators is None:
        feature = _feature()
        reference, _ = _p2b("P2B-CONFIG", (feature,))
        resonators = _scope(feature, reference).resonators
    return {
        "schema_version": "1.0.0",
        "enabled": True,
        "provisional": True,
        "input_feature_kind": "dense_raw_spl",
        "normalization": "none",
        "peak_algorithm": "scipy_topographic_prominence",
        "peak_selection_rule": "prominence_then_magnitude_then_lowest_frequency",
        "search_band_overlap_policy": "reject",
        "drift": {"minimum_valid_peaks": 2, "reference": "median_peak_frequency"},
        "energy_fraction": {"missing_resonator_policy": "require_all", "sum_tolerance": 1.0e-12},
        "resonators": [_resonator_config(item) for item in resonators],
    }


def _triangular_feature(*, invalid_frequency: float | None = None) -> FeatureSet:
    feature = _feature()
    frequency = np.arange(1400.0, 1600.0 + 10.0, 10.0)
    values = 10.0 - np.abs(frequency - 1500.0) / 10.0
    mask = np.ones(frequency.size, dtype=bool)
    if invalid_frequency is not None:
        mask[np.flatnonzero(frequency == invalid_frequency)[0]] = False
    return replace(
        feature,
        feature_names=tuple(f"f_{value:g}_hz" for value in frequency),
        values=values,
        valid_mask=mask,
        units=("dB",) * frequency.size,
    )


def test_hr_calibration_scope_round_trip_and_hash() -> None:
    feature = _feature()
    reference, _ = _p2b("P2B-HR", (feature,))
    scope = _scope(feature, reference)

    restored = HRCalibrationScope.from_dict(scope.to_dict())

    assert restored == scope
    assert scope.sha256.startswith("sha256:")
    assert len(scope.sha256) == 71


def test_known_peak_is_selected_from_data_not_design_target_or_filename() -> None:
    feature = _feature(peak_hz=1500.0)
    reference, p2b = _p2b("P2B-HR", (feature,))
    result = analyze_sweep_hr_calibration((feature,), _scope(feature, reference), p2b, _config())

    peak = result.detected_peaks[0]
    assert peak.status == "available"
    assert peak.peak_frequency_hz == pytest.approx(1500.0, abs=1e-9)
    assert peak.peak_frequency_hz != 1700.0
    assert result.calibration_status == "software_validation_only"
    assert result.scientifically_eligible is False


def test_sparse_or_normalized_feature_contract_is_rejected() -> None:
    feature = _feature()
    reference, p2b = _p2b("P2B-HR", (feature,))
    scope = _scope(feature, reference)

    bad = replace(
        feature,
        feature_kind=FeatureKind.DENSE_ZSCORE,
        normalization_method="zscore_spectrum",
        units=("dimensionless",) * len(feature.units),
    )
    with pytest.raises(HRInputError, match="dense_raw_spl"):
        analyze_sweep_hr_calibration((bad,), scope, p2b, _config())


def test_crossings_bandwidth_q_energy_and_fraction_use_configured_math() -> None:
    feature = _triangular_feature()
    reference, p2b = _p2b("P2B-HR", (feature,))
    result = analyze_sweep_hr_calibration((feature,), _scope(feature, reference), p2b, _config())

    bandwidth = result.bandwidths[0]
    expected_half_width = 10.0 * 3.010299956639812
    assert bandwidth.status == "available"
    assert bandwidth.left_crossing_hz == pytest.approx(1500.0 - expected_half_width)
    assert bandwidth.right_crossing_hz == pytest.approx(1500.0 + expected_half_width)
    assert bandwidth.bandwidth_hz == pytest.approx(2.0 * expected_half_width)
    assert bandwidth.q_factor == pytest.approx(1500.0 / (2.0 * expected_half_width))

    energy = result.integrated_energies[0]
    assert energy.status == "available"
    assert energy.energy_linear_hz is not None and energy.energy_linear_hz > 0.0
    assert energy.integration_domain == "linear_power_ratio"
    fraction = result.energy_fractions[0]
    assert fraction.q_i == pytest.approx(1.0, abs=1e-12)


def test_invalid_gap_is_never_crossed_for_bandwidth() -> None:
    feature = _triangular_feature(invalid_frequency=1460.0)
    reference, p2b = _p2b("P2B-HR", (feature,))
    result = analyze_sweep_hr_calibration((feature,), _scope(feature, reference), p2b, _config())

    bandwidth = result.bandwidths[0]
    assert bandwidth.status == "unavailable"
    assert bandwidth.left_crossing_hz is None
    assert bandwidth.reason == "left_crossing_unavailable"
    assert result.integrated_energies[0].status == "unavailable"
    assert result.energy_fractions[0].status == "unavailable"


def test_peak_drift_is_grouped_separately_by_repeat_type() -> None:
    features = (
        _feature("cont-1", peak_hz=1499.0, repeat_type="CONT"),
        _feature("cont-2", peak_hz=1501.0, repeat_type="CONT"),
        _feature("repos-1", peak_hz=1495.0, repeat_type="REPOS"),
        _feature("repos-2", peak_hz=1505.0, repeat_type="REPOS"),
        _feature("reasm-1", peak_hz=1490.0, repeat_type="REASM"),
        _feature("reasm-2", peak_hz=1510.0, repeat_type="REASM"),
    )
    reference, p2b = _p2b("P2B-HR-MULTI", features)
    result = analyze_sweep_hr_calibration(features, _scope_many(features, reference), p2b, _config())

    by_type = {item.repeat_type: item for item in result.peak_drifts}
    assert set(by_type) == {"CONT", "REPOS", "REASM"}
    assert by_type["CONT"].peak_to_peak_hz == pytest.approx(2.0)
    assert by_type["REPOS"].peak_to_peak_hz == pytest.approx(10.0)
    assert by_type["REASM"].peak_to_peak_hz == pytest.approx(20.0)
    assert all(item.valid_peak_count == 2 for item in by_type.values())
    assert by_type["CONT"].sample_ids == ("cont-1", "cont-2")


def test_pairwise_overlap_and_two_resonator_energy_fractions() -> None:
    base = _feature()
    frequency = np.arange(1300.0, 1801.0, 1.0)
    values = np.maximum(
        10.0 - np.abs(frequency - 1500.0) * 0.05,
        10.0 - np.abs(frequency - 1580.0) * 0.05,
    )
    feature = replace(
        base,
        feature_names=tuple(f"f_{value:g}_hz" for value in frequency),
        values=values,
        valid_mask=np.ones(values.size, dtype=bool),
        units=("dB",) * values.size,
    )
    reference, p2b = _p2b("P2B-HR-OVERLAP", (feature,))
    scope = _scope(feature, reference)
    r1 = replace(
        scope.resonators[0],
        resonator_id="R1",
        search_min_hz=1400.0,
        search_max_hz=1540.0,
        boundary="left_closed_right_open",
        minimum_prominence_db=1.5,
    )
    r2 = replace(
        r1,
        resonator_id="R2",
        search_min_hz=1540.0,
        search_max_hz=1680.0,
        boundary="closed",
    )
    member = replace(scope.members[0], resonator_ids=("R1", "R2"))
    scope = replace(scope, members=(member,), resonators=(r1, r2))

    result = analyze_sweep_hr_calibration((feature,), scope, p2b, _config(scope.resonators))

    assert [item.peak_frequency_hz for item in result.detected_peaks] == [1500.0, 1580.0]
    overlap = result.peak_overlaps[0]
    assert overlap.status == "available"
    assert overlap.overlap_hz is not None and overlap.overlap_hz > 0.0
    assert overlap.overlap_fraction_of_narrower == pytest.approx(1.0)
    fractions = {item.resonator_id: item.q_i for item in result.energy_fractions}
    assert fractions == pytest.approx({"R1": 0.5, "R2": 0.5}, abs=1e-12)

    missing_r2 = replace(r2, minimum_prominence_db=2.1)
    missing_scope = replace(scope, resonators=(r1, missing_r2))
    required = analyze_sweep_hr_calibration(
        (feature,), missing_scope, p2b, _config(missing_scope.resonators)
    )
    assert required.peak_overlaps[0].status == "unavailable"
    assert all(item.status == "unavailable" and item.q_i is None for item in required.energy_fractions)
    partial_config = _config(missing_scope.resonators)
    partial_config["energy_fraction"]["missing_resonator_policy"] = "allow_partial"
    partial = analyze_sweep_hr_calibration((feature,), missing_scope, p2b, partial_config)
    by_id = {item.resonator_id: item for item in partial.energy_fractions}
    assert by_id["R1"].status == "partial" and by_id["R1"].q_i == pytest.approx(1.0)
    assert by_id["R2"].status == "partial" and by_id["R2"].q_i is None


def test_equal_multi_peak_tie_break_selects_lower_frequency() -> None:
    base = _feature()
    frequency = np.arange(1400.0, 1601.0, 1.0)
    values = np.zeros(frequency.size)
    values[frequency == 1450.0] = 10.0
    values[frequency == 1550.0] = 10.0
    feature = replace(base, feature_names=tuple(f"f_{value:g}_hz" for value in frequency), values=values,
                      valid_mask=np.ones(values.size, dtype=bool), units=("dB",) * values.size)
    reference, p2b = _p2b("P2B-TIE", (feature,))
    scope = _scope(feature, reference)
    spec = replace(scope.resonators[0], search_min_hz=1400.0, search_max_hz=1600.0)
    scope = replace(scope, resonators=(spec,))

    result = analyze_sweep_hr_calibration((feature,), scope, p2b, _config(scope.resonators))

    assert result.detected_peaks[0].candidate_peak_count == 2
    assert result.detected_peaks[0].peak_frequency_hz == 1450.0
    assert sum(item.selected for item in result.candidates) == 1


def test_no_peak_and_prominence_threshold_are_explicitly_unavailable() -> None:
    base = _feature()
    flat = replace(base, values=np.zeros_like(base.values))
    reference, p2b = _p2b("P2B-NO-PEAK", (flat,))
    scope = _scope(flat, reference)
    result = analyze_sweep_hr_calibration((flat,), scope, p2b, _config(scope.resonators))
    assert result.detected_peaks[0].status == "unavailable"
    assert result.detected_peaks[0].reason == "no_qualified_local_peak"

    triangular = _triangular_feature()
    reference, p2b = _p2b("P2B-PROM", (triangular,))
    scope = _scope(triangular, reference)
    exact = replace(scope.resonators[0], minimum_prominence_db=10.0)
    exact_scope = replace(scope, resonators=(exact,))
    assert analyze_sweep_hr_calibration((triangular,), exact_scope, p2b, _config((exact,))).detected_peaks[0].status == "available"
    above = replace(exact, minimum_prominence_db=10.0 + 1e-9)
    above_scope = replace(scope, resonators=(above,))
    assert analyze_sweep_hr_calibration((triangular,), above_scope, p2b, _config((above,))).detected_peaks[0].status == "unavailable"


def test_non_authoritative_or_nonmonotonic_frequency_axis_is_rejected() -> None:
    feature = _feature()
    reference, p2b = _p2b("P2B-AXIS", (feature,))
    scope = _scope(feature, reference)
    bad = replace(feature, feature_names=(feature.feature_names[1], feature.feature_names[0], *feature.feature_names[2:]))
    with pytest.raises(HRInputError, match="strictly increasing"):
        analyze_sweep_hr_calibration((bad,), scope, p2b, _config(scope.resonators))


def test_p2b_hash_mismatch_and_simulated_approved_state_are_rejected() -> None:
    feature = _feature()
    reference, p2b = _p2b("P2B-GATE", (feature,))
    scope = _scope(feature, reference)
    with pytest.raises(HRInputError, match="P2-B gate failed"):
        analyze_sweep_hr_calibration((feature,), scope, replace(p2b, config_sha256="sha256:" + "9" * 64), _config(scope.resonators))

    approval = ApprovalRecord("approval-1", "reviewer", "2026-08-06T12:00:00+00:00", "sha256:" + "a" * 64)
    requested = replace(scope, requested_calibration_status="approved_real_calibration", approval_record=approval, thresholds_frozen=True)
    with pytest.raises(HRInputError, match="research_analysis"):
        analyze_sweep_hr_calibration((feature,), requested, p2b, _config(scope.resonators))


def test_final_test_member_is_rejected_when_scope_is_constructed() -> None:
    feature = _feature()
    reference, _ = _p2b("P2B-FINAL", (feature,))
    scope = _scope(feature, reference)
    with pytest.raises(HRInputError, match="final_test"):
        replace(scope.members[0], cohort_role="final_test")


def test_implicit_cross_configuration_or_session_pooling_is_rejected() -> None:
    feature = _feature()
    reference, _ = _p2b("P2B-POOL", (feature,))
    scope = _scope(feature, reference)
    with pytest.raises(HRInputError, match="cross-configuration"):
        replace(scope, groups=(replace(scope.groups[0], configuration_id="OTHER"),))
    with pytest.raises(HRInputError, match="pooling dimension"):
        replace(scope, groups=(replace(scope.groups[0], session_ids=("S99",)),))


def test_fixed_integration_window_reports_gap_coverage_without_bridging() -> None:
    feature = _triangular_feature(invalid_frequency=1460.0)
    reference, p2b = _p2b("P2B-COVERAGE", (feature,))
    scope = _scope(feature, reference)
    strict = replace(
        scope.resonators[0],
        integration_method="fixed_half_width_around_measured_peak",
        integration_half_width_hz=50.0,
        minimum_integration_coverage=1.0,
    )
    strict_scope = replace(scope, resonators=(strict,))
    strict_result = analyze_sweep_hr_calibration((feature,), strict_scope, p2b, _config((strict,)))
    assert strict_result.integrated_energies[0].status == "unavailable"
    assert strict_result.integrated_energies[0].coverage_fraction == pytest.approx(0.8)

    permissive = replace(strict, minimum_integration_coverage=0.8)
    permissive_scope = replace(scope, resonators=(permissive,))
    permissive_result = analyze_sweep_hr_calibration((feature,), permissive_scope, p2b, _config((permissive,)))
    assert permissive_result.integrated_energies[0].status == "available"
    assert permissive_result.integrated_energies[0].valid_segment_count == 1
