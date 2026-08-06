from __future__ import annotations

from acoustic_encoder.dataset_quality_control import DatasetQCReference
from acoustic_encoder.hr_analysis import ApprovalRecord, CalibrationStatus, FinalTestSeal
from dataclasses import replace

from acoustic_encoder.hr_analysis import analyze_sweep_hr_calibration
from acoustic_encoder.hr_readout import (
    CalibrationAuthority,
    CalibrationResonatorWindow,
    HRCalibrationReference,
    HRReadoutScope,
    HRReadoutScopeMember,
    analyze_multisine_hr_readout,
    readout_multisine_feature,
    _validate_calibration_lifecycle,
)
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    FeatureKind,
    FeatureQualityRecord,
    FeatureSet,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    QCStatus,
    Representation,
    SourceFormat,
)
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET
from acoustic_encoder.dataset_quality_control import (
    feature_contract_sha256,
    feature_set_content_sha256,
)
from test_hr_analysis import _config as _p6a_config
from test_hr_analysis import _feature as _p6a_feature
from test_hr_analysis import _p2b
from test_hr_analysis import _scope as _p6a_scope

import numpy as np
import pytest


def _digest(character: str) -> str:
    return "sha256:" + character * 64


def test_hr_readout_scope_round_trip_preserves_explicit_inputs_and_hash() -> None:
    member = HRReadoutScopeMember(
        sample_id="ms-1",
        feature_base_path="artifacts/ms-1",
        feature_npz_sha256="1" * 64,
        feature_json_sha256="2" * 64,
        feature_content_sha256=_digest("3"),
        feature_contract_sha256=_digest("4"),
        configuration_id="U4ENC",
        direction_id="A000",
        direction_angle_deg=0.0,
        session_id="S01",
        repeat_type="CONT",
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        selection_reason="explicit simulated validation",
        tone_set_id="tones-v1",
        tone_set_sha256="5" * 64,
        stimulus_id="stimulus-v1",
        stimulus_sha256="6" * 64,
        magnitude_quantity="transfer_ratio",
        magnitude_reference=_digest("6"),
        cohort_role="development",
    )
    calibration = HRCalibrationReference(
        calibration_id=_digest("7"),
        calibration_json_path="calibration/hr_calibration.json",
        calibration_json_sha256="8" * 64,
        calibration_manifest_path="calibration/hr_calibration_manifest.json",
        calibration_manifest_sha256="9" * 64,
        calibration_manifest_digest_path="calibration/hr_calibration_manifest.sha256",
        calibration_manifest_digest_sha256="a" * 64,
    )
    scope = HRReadoutScope(
        schema_version="1.0.0",
        hr_readout_scope_id="P6B-SCOPE-1",
        members=(member,),
        calibration_reference=calibration,
        calibration_group_id="G1",
        resonator_ids=("R1", "R2", "R3"),
        mapping_method="nearest_tone",
        integration_method="nearest_tone_power",
        p2b_reference=DatasetQCReference("P2B-MS", _digest("b")),
        final_test_seal=FinalTestSeal(
            sealed=True,
            partition_sha256=_digest("c"),
            excluded_sample_ids=("final-1",),
        ),
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        random_state=20260806,
    )

    restored = HRReadoutScope.from_dict(scope.to_dict())

    assert restored == scope
    assert restored.sha256 == scope.sha256
    assert restored.ordered_sample_ids == ("ms-1",)


def _tone_feature(
    frequencies: tuple[float, ...], values_db: tuple[float, ...]
) -> FeatureSet:
    names = tuple(
        f"tone_{index:06d}_{frequency:g}_hz"
        for index, frequency in enumerate(frequencies)
    )
    meta = MeasurementMeta(
        sample_id="ms-1",
        **SCHEMA_VERSION_QUARTET,
        device_version="V2",
        configuration="U4ENC",
        angle_deg=0.0,
        session_id="S01",
        repeat_type="CONT",
        repeat_id="R01",
        experiment_step="DEV_C11",
        measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        source_format=SourceFormat.MOCK_AUDIO,
        source_path="recording.wav",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256="d" * 64,
        provenance_uri="mock://DEV-C11",
        eligible_for_scientific_analysis=False,
        stimulus_id="stimulus-v1",
        stimulus_hash="6" * 64,
        tone_set_id="tones-v1",
        sidecar_path="recording.json",
        audio_channel=0,
    )
    return FeatureSet(
        sample_id=meta.sample_id,
        feature_schema_version=meta.feature_schema_version,
        feature_kind=FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
        feature_names=names,
        values=np.asarray(values_db),
        valid_mask=np.ones(len(names), dtype=bool),
        units=("dB",) * len(names),
        source_measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        source_representation=Representation.SPARSE_TONES,
        preprocessing_id=_digest("e"),
        meta=meta,
        tone_set_id="tones-v1",
        tone_set_sha256="5" * 64,
        tone_schema_id=_digest("f"),
        normalization_method="none",
        source_magnitude_quantity="transfer_ratio",
        source_magnitude_reference=_digest("6"),
        source_phase_status=PhaseStatus.RELATIVE_UNRELIABLE,
        source_qc_status=QCStatus.VALID,
        source_qc_sha256=_digest("a"),
        source_qc_eligible_for_downstream=True,
        feature_quality=tuple(
            FeatureQualityRecord(
                feature_name=name,
                availability="available",
                valid=True,
                reason_codes=(),
                source_module="P8_P3_C",
                details={
                    "frequency_hz": frequency,
                    "missing_tone": False,
                    "snr_db": 60.0,
                    "snr_status": "valid",
                    "leakage_status": "valid",
                    "period_variance_status": "valid",
                },
            )
            for name, frequency in zip(names, frequencies, strict=True)
        ),
    )


def _readout_config(method: str) -> dict:
    return {
        "schema_version": "1.0.0",
        "enabled": True,
        "provisional": True,
        "input_feature_kind": "tone_measurement_from_multisine",
        "input_representation": "sparse_tones",
        "normalization": "none",
        "phase_policy": "magnitude_only",
        "tone_mapping": {
            "method": method,
            "allow_shared_tones": False,
            "maximum_detuning_hz": 15.0,
        },
        "coverage": {
            "minimum_valid_tones": 1 if method == "nearest_tone" else 3,
            "minimum_coverage_fraction": 1.0,
            "maximum_tone_gap_hz": 10.0,
            "endpoint_tolerance_hz": 0.0,
            "missing_tone_policy": "unavailable",
        },
        "energy": {
            "method": (
                "nearest_tone_power"
                if method == "nearest_tone"
                else "narrowband_trapezoid"
            ),
            "conversion": "ten_power_db_over_10",
        },
        "energy_fraction": {
            "emit_feature_set": True,
            "missing_resonator_policy": "require_all",
            "sum_tolerance": 1.0e-12,
        },
        "uncertainty": {"method": "unavailable"},
    }


def _software_lifecycle_inputs():
    calibration_feature = _p6a_feature()
    reference, p2b = _p2b("P2B-LIFECYCLE", (calibration_feature,))
    calibration_scope = _p6a_scope(calibration_feature, reference)
    calibration_config = _p6a_config()
    result = analyze_sweep_hr_calibration(
        (calibration_feature,), calibration_scope, p2b, calibration_config,
        created_at_utc="2026-08-06T12:00:00+00:00",
    )
    authority = CalibrationAuthority(
        result, calibration_scope, calibration_config, "8" * 64, "9" * 64
    )
    source = replace(_tone_feature((1500.0,), (0.0,)), meta=replace(
        _tone_feature((1500.0,), (0.0,)).meta, configuration="HR-SIM"
    ))
    member = HRReadoutScopeMember(
        source.sample_id, "features/ms-1", "1" * 64, "2" * 64,
        feature_set_content_sha256(source), feature_contract_sha256(source),
        "HR-SIM", "A000", 0.0, "S01", "CONT",
        DatasetRole.SOFTWARE_VALIDATION, "explicit lifecycle fixture",
        source.tone_set_id, source.tone_set_sha256, source.meta.stimulus_id,
        source.meta.stimulus_hash, source.source_magnitude_quantity,
        source.source_magnitude_reference, "development",
    )
    readout_reference, readout_p2b = _p2b("P2B-READOUT-LIFECYCLE", (source,))
    scope = HRReadoutScope(
        "1.0.0", "P6B-LIFECYCLE", (member,),
        HRCalibrationReference(
            result.calibration_id, "cal/hr_calibration.json", "8" * 64,
            "cal/hr_calibration_manifest.json", "9" * 64,
            "cal/hr_calibration_manifest.sha256", "a" * 64,
        ),
        "G1", ("R1",), "nearest_tone", "nearest_tone_power",
        readout_reference,
        calibration_scope.final_test_seal, RunPurpose.SOFTWARE_VALIDATION,
        DataOrigin.SIMULATED, DatasetRole.SOFTWARE_VALIDATION, 20260806,
    )
    return authority, scope, source, readout_p2b


def test_nearest_tone_readout_uses_measured_peak_and_linear_power() -> None:
    feature = _tone_feature((1000.0, 1020.0), (10.0, 0.0))
    result = readout_multisine_feature(
        feature,
        (CalibrationResonatorWindow("R1", 1003.0, 1003.0, 1003.0, "nearest_tone"),),
        _readout_config("nearest_tone"),
    )

    mapping = result.mappings[0]
    energy = result.band_energies[0]
    assert mapping.selected_tone_frequencies_hz == (1000.0,)
    assert mapping.signed_detuning_hz == -3.0
    assert mapping.absolute_detuning_hz == 3.0
    assert energy.status == "valid"
    assert energy.energy_value == 10.0
    assert energy.units == "relative_tone_power"


def test_calibrated_window_integrates_segments_and_recovers_energy_fraction() -> None:
    feature = _tone_feature(
        (1000.0, 1010.0, 1020.0, 1100.0, 1110.0, 1120.0),
        (0.0, 0.0, 0.0, 3.010299956639812, 3.010299956639812, 3.010299956639812),
    )
    result = readout_multisine_feature(
        feature,
        (
            CalibrationResonatorWindow("R1", 1010.0, 1000.0, 1020.0, "calibrated_window"),
            CalibrationResonatorWindow("R2", 1110.0, 1100.0, 1120.0, "calibrated_window"),
        ),
        _readout_config("calibrated_window"),
    )

    np.testing.assert_allclose(
        [item.energy_value for item in result.band_energies], [20.0, 40.0]
    )
    np.testing.assert_allclose(
        [item.q_i for item in result.energy_fractions], [1.0 / 3.0, 2.0 / 3.0]
    )
    assert sum(item.q_i for item in result.energy_fractions if item.q_i is not None) == 1.0


def test_full_software_validation_readout_propagates_lifecycle_and_feature_links() -> None:
    calibration_feature = _p6a_feature()
    calibration_reference, calibration_p2b = _p2b("P2B-CAL", (calibration_feature,))
    calibration_scope = _p6a_scope(calibration_feature, calibration_reference)
    calibration_config = _p6a_config()
    calibration_result = analyze_sweep_hr_calibration(
        (calibration_feature,), calibration_scope, calibration_p2b, calibration_config,
        created_at_utc="2026-08-06T12:00:00+00:00",
    )
    authority = CalibrationAuthority(
        calibration_result,
        calibration_scope,
        calibration_config,
        "8" * 64,
        "9" * 64,
    )
    source = _tone_feature((1490.0, 1500.0, 1510.0), (0.0, 10.0, 0.0))
    source = replace(source, meta=replace(source.meta, configuration="HR-SIM"))
    readout_reference, readout_p2b = _p2b("P2B-READOUT", (source,))
    member = HRReadoutScopeMember(
        sample_id=source.sample_id,
        feature_base_path="features/ms-1",
        feature_npz_sha256="1" * 64,
        feature_json_sha256="2" * 64,
        feature_content_sha256=feature_set_content_sha256(source),
        feature_contract_sha256=feature_contract_sha256(source),
        configuration_id="HR-SIM",
        direction_id="A000",
        direction_angle_deg=0.0,
        session_id="S01",
        repeat_type="CONT",
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        selection_reason="explicit simulated readout",
        tone_set_id=source.tone_set_id,
        tone_set_sha256=source.tone_set_sha256,
        stimulus_id=source.meta.stimulus_id,
        stimulus_sha256=source.meta.stimulus_hash,
        magnitude_quantity=source.source_magnitude_quantity,
        magnitude_reference=source.source_magnitude_reference,
        cohort_role="development",
    )
    scope = HRReadoutScope(
        schema_version="1.0.0",
        hr_readout_scope_id="P6B-SCOPE",
        members=(member,),
        calibration_reference=HRCalibrationReference(
            calibration_result.calibration_id,
            "cal/hr_calibration.json",
            "8" * 64,
            "cal/hr_calibration_manifest.json",
            "9" * 64,
            "cal/hr_calibration_manifest.sha256",
            "a" * 64,
        ),
        calibration_group_id="G1",
        resonator_ids=("R1",),
        mapping_method="nearest_tone",
        integration_method="nearest_tone_power",
        p2b_reference=readout_reference,
        final_test_seal=calibration_scope.final_test_seal,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        random_state=20260806,
    )

    analysis = analyze_multisine_hr_readout(
        (source,), scope, readout_p2b, authority, _readout_config("nearest_tone"),
        created_at_utc="2026-08-06T13:00:00+00:00",
    )

    assert analysis.result.readout_status == "software_validation_only"
    assert analysis.result.scientifically_eligible is False
    assert analysis.result.deployment_allowed is False
    assert analysis.result.absolute_energy_comparable is False
    assert analysis.result.absolute_comparability_reason == "no_cross_mode_amplitude_calibration"
    energy = analysis.hr_band_energy_features[0]
    fraction = analysis.hr_energy_fraction_features[0]
    assert energy.calibration_id == calibration_result.calibration_id
    assert energy.derivation is not None
    assert energy.derivation.source_feature_content_sha256 == feature_set_content_sha256(source)
    assert energy.source_phase_status is PhaseStatus.RELATIVE_UNRELIABLE
    assert energy.feature_kind is FeatureKind.HR_BAND_ENERGY
    assert fraction.feature_kind is FeatureKind.HR_ENERGY_FRACTION
    assert energy.units == ("relative_tone_power",)
    assert fraction.units == ("dimensionless",)
    assert energy.derivation.calibration_json_sha256 == "8" * 64
    assert energy.derivation.calibration_manifest_sha256 == "9" * 64
    assert energy.derivation.p2b_result_sha256 == readout_reference.dataset_qc_result_sha256
    np.testing.assert_allclose(fraction.values, [1.0])

    with pytest.raises(ValueError, match="scope/config method mismatch"):
        analyze_multisine_hr_readout(
            (source,), scope, readout_p2b, authority,
            _readout_config("calibrated_window"),
        )


def test_detuning_limit_and_duplicate_assignment_are_explicitly_unavailable() -> None:
    feature = _tone_feature((1000.0,), (10.0,))
    detuned = readout_multisine_feature(
        feature,
        (CalibrationResonatorWindow("R1", 1020.0, 1020.0, 1020.0, "nearest_tone"),),
        _readout_config("nearest_tone"),
    )
    assert detuned.band_energies[0].energy_value is None
    assert "maximum_detuning_exceeded" in detuned.band_energies[0].reasons

    collision = readout_multisine_feature(
        feature,
        (
            CalibrationResonatorWindow("R1", 1000.0, 1000.0, 1000.0, "nearest_tone"),
            CalibrationResonatorWindow("R2", 1001.0, 1001.0, 1001.0, "nearest_tone"),
        ),
        _readout_config("nearest_tone"),
    )
    assert all(item.energy_value is None for item in collision.band_energies)
    assert all("tone_assignment_conflict" in item.reasons for item in collision.band_energies)


def test_window_does_not_bridge_missing_or_invalid_tone() -> None:
    feature = _tone_feature((1000.0, 1010.0, 1020.0), (0.0, 0.0, 0.0))
    quality = list(feature.feature_quality)
    quality[1] = FeatureQualityRecord(
        feature_name=feature.feature_names[1],
        availability="missing",
        valid=False,
        reason_codes=("missing_tone",),
        source_module="P8_P3_C",
        details={"missing_tone": True},
    )
    feature = replace(
        feature,
        valid_mask=np.array([True, False, True]),
        values=np.array([0.0, np.nan, 0.0]),
        feature_quality=tuple(quality),
    )
    config = _readout_config("calibrated_window")
    config["coverage"]["minimum_valid_tones"] = 2
    config["coverage"]["minimum_coverage_fraction"] = 0.1
    config["coverage"]["maximum_tone_gap_hz"] = 25.0
    result = readout_multisine_feature(
        feature,
        (CalibrationResonatorWindow("R1", 1010.0, 1000.0, 1020.0, "calibrated_window"),),
        config,
    )

    assert result.coverages[0].missing_tone_ids == (feature.feature_names[1],)
    assert result.coverages[0].integration_segments_hz == ()
    assert result.band_energies[0].energy_value is None


def test_allow_partial_q_keeps_missing_resonator_nan_instead_of_zero() -> None:
    feature = _tone_feature((1000.0,), (10.0,))
    config = _readout_config("nearest_tone")
    config["energy_fraction"]["missing_resonator_policy"] = "allow_partial"
    result = readout_multisine_feature(
        feature,
        (
            CalibrationResonatorWindow("R1", 1000.0, 1000.0, 1000.0, "nearest_tone"),
            CalibrationResonatorWindow("R2", 1030.0, 1030.0, 1030.0, "nearest_tone"),
        ),
        config,
    )

    assert result.energy_fractions[0].q_i == 1.0
    assert result.energy_fractions[0].status == "partial"
    assert result.energy_fractions[1].q_i is None
    assert result.energy_fractions[1].energy_value is None


def test_require_all_makes_entire_fraction_group_unavailable() -> None:
    feature = _tone_feature((1000.0,), (10.0,))
    result = readout_multisine_feature(
        feature,
        (
            CalibrationResonatorWindow("R1", 1000.0, 1000.0, 1000.0, "nearest_tone"),
            CalibrationResonatorWindow("R2", 1030.0, 1030.0, 1030.0, "nearest_tone"),
        ),
        _readout_config("nearest_tone"),
    )

    assert all(item.q_i is None for item in result.energy_fractions)
    assert all(item.status == "unavailable" for item in result.energy_fractions)


def test_explicit_tone_sharing_can_be_enabled_and_is_audited() -> None:
    feature = _tone_feature((1000.0,), (10.0,))
    config = _readout_config("nearest_tone")
    config["tone_mapping"]["allow_shared_tones"] = True
    result = readout_multisine_feature(
        feature,
        (
            CalibrationResonatorWindow("R1", 1000.0, 1000.0, 1000.0, "nearest_tone"),
            CalibrationResonatorWindow("R2", 1001.0, 1001.0, 1001.0, "nearest_tone"),
        ),
        config,
    )

    assert all(item.shared_assignment for item in result.mappings)
    assert all(item.energy_value == 10.0 for item in result.band_energies)


def test_invalid_tone_is_distinct_from_missing_and_single_tone_is_not_integrated() -> None:
    feature = _tone_feature((1000.0, 1010.0, 1020.0), (0.0, 0.0, 0.0))
    quality = list(feature.feature_quality)
    quality[1] = FeatureQualityRecord(
        feature.feature_names[1], "invalid", False, ("low_snr",), "P8_P3_C",
        {"missing_tone": False, "snr_status": "exclude_candidate"},
    )
    feature = replace(
        feature,
        values=np.asarray([0.0, np.nan, np.nan]),
        valid_mask=np.asarray([True, False, False]),
        feature_quality=(quality[0], quality[1], replace(
            quality[2], availability="missing", valid=False,
            reason_codes=("missing_tone",)
        )),
    )
    config = _readout_config("calibrated_window")
    config["coverage"]["minimum_valid_tones"] = 2
    config["coverage"]["minimum_coverage_fraction"] = 0.1
    result = readout_multisine_feature(
        feature,
        (CalibrationResonatorWindow("R1", 1010.0, 1000.0, 1020.0, "window"),),
        config,
    )

    coverage = result.coverages[0]
    assert coverage.invalid_tone_ids == (feature.feature_names[1],)
    assert coverage.missing_tone_ids == (feature.feature_names[2],)
    assert result.band_energies[0].energy_value is None


@pytest.mark.parametrize(
    ("frequencies", "coverage_change", "reason"),
    [
        ((1000.0, 1020.0), {"minimum_valid_tones": 3}, "minimum_valid_tones_not_met"),
        ((1000.0, 1010.0), {"minimum_coverage_fraction": 0.75}, "minimum_coverage_fraction_not_met"),
        ((1000.0, 1010.0, 1020.0), {"maximum_tone_gap_hz": 9.0}, "maximum_tone_gap_exceeded"),
        ((1002.0, 1010.0, 1018.0), {"endpoint_tolerance_hz": 1.0}, "endpoint_coverage_not_met"),
    ],
)
def test_window_coverage_gates_are_independent_and_auditable(
    frequencies: tuple[float, ...], coverage_change: dict[str, float], reason: str
) -> None:
    feature = _tone_feature(frequencies, (0.0,) * len(frequencies))
    config = _readout_config("calibrated_window")
    config["coverage"].update({
        "minimum_valid_tones": 2,
        "minimum_coverage_fraction": 0.5,
        "maximum_tone_gap_hz": 20.0,
        "endpoint_tolerance_hz": 2.0,
        **coverage_change,
    })
    result = readout_multisine_feature(
        feature,
        (CalibrationResonatorWindow("R1", 1010.0, 1000.0, 1020.0, "window"),),
        config,
    )

    assert reason in result.coverages[0].reasons
    assert result.band_energies[0].status == "unavailable"


def test_endpoint_and_threshold_equalities_pass_without_extrapolation() -> None:
    feature = _tone_feature((1002.0, 1010.0, 1018.0), (0.0, 0.0, 0.0))
    config = _readout_config("calibrated_window")
    config["coverage"].update({
        "minimum_valid_tones": 3,
        "minimum_coverage_fraction": 0.8,
        "maximum_tone_gap_hz": 8.0,
        "endpoint_tolerance_hz": 2.0,
    })
    result = readout_multisine_feature(
        feature,
        (CalibrationResonatorWindow("R1", 1010.0, 1000.0, 1020.0, "window"),),
        config,
    )

    coverage = result.coverages[0]
    assert coverage.status == "valid"
    assert coverage.coverage_fraction == 0.8
    assert coverage.integration_segments_hz == ((1002.0, 1018.0),)
    assert result.band_energies[0].energy_value == 16.0


def test_upstream_exclude_is_preserved_without_deleting_computed_energy() -> None:
    feature = replace(
        _tone_feature((1000.0,), (10.0,)),
        source_qc_status=QCStatus.EXCLUDE_CANDIDATE,
    )
    result = readout_multisine_feature(
        feature,
        (CalibrationResonatorWindow("R1", 1000.0, 1000.0, 1000.0, "nearest_tone"),),
        _readout_config("nearest_tone"),
    )

    assert result.band_energies[0].status == "exclude_candidate"
    assert result.band_energies[0].energy_value == 10.0
    assert "upstream_qc_exclude_candidate" in result.band_energies[0].reasons


@pytest.mark.parametrize(
    ("status", "superseded_by", "message"),
    [
        (CalibrationStatus.DRAFT, None, "draft calibration"),
        (CalibrationStatus.SUPERSEDED, _digest("d"), "superseded calibration"),
    ],
)
def test_draft_and_superseded_calibrations_are_rejected(
    status: CalibrationStatus, superseded_by: str | None, message: str
) -> None:
    authority, scope, _, _ = _software_lifecycle_inputs()
    result = replace(
        authority.result,
        calibration_status=status,
        superseded_by=superseded_by,
    )
    authority = replace(authority, result=result)
    scope = replace(
        scope,
        calibration_reference=replace(
            scope.calibration_reference, calibration_id=result.calibration_id
        ),
    )

    with pytest.raises(ValueError, match=message):
        _validate_calibration_lifecycle(authority, scope)


def test_software_validation_calibration_cannot_authorize_real_readout() -> None:
    authority, scope, _, _ = _software_lifecycle_inputs()
    member = replace(scope.members[0], dataset_role=DatasetRole.RESEARCH_INPUT)
    real_scope = replace(
        scope,
        members=(member,),
        run_purpose=RunPurpose.RESEARCH_ANALYSIS,
        data_origin=DataOrigin.REAL_EXPERIMENT,
        dataset_role=DatasetRole.RESEARCH_INPUT,
    )

    with pytest.raises(ValueError, match="software-validation calibration"):
        _validate_calibration_lifecycle(authority, real_scope)


def test_approved_status_cannot_upgrade_a_simulated_calibration_authority() -> None:
    authority, scope, _, _ = _software_lifecycle_inputs()
    approval = ApprovalRecord(
        "approval-1", "reviewer", "2026-08-06T12:00:00+00:00", _digest("e")
    )
    result = replace(
        authority.result,
        calibration_status=CalibrationStatus.APPROVED_REAL_CALIBRATION,
        frozen_for_research=True,
        scientifically_eligible=True,
        approval_record=approval,
    )
    authority = replace(authority, result=result)
    member = replace(scope.members[0], dataset_role=DatasetRole.RESEARCH_INPUT)
    real_scope = replace(
        scope,
        members=(member,),
        calibration_reference=replace(
            scope.calibration_reference, calibration_id=result.calibration_id
        ),
        run_purpose=RunPurpose.RESEARCH_ANALYSIS,
        data_origin=DataOrigin.REAL_EXPERIMENT,
        dataset_role=DatasetRole.RESEARCH_INPUT,
    )

    with pytest.raises(ValueError, match="approved-real calibration hard gate"):
        _validate_calibration_lifecycle(authority, real_scope)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("calibration_id", _digest("0"), "semantic ID"),
        ("calibration_json_sha256", "0" * 64, "exact-file hash"),
        ("calibration_manifest_sha256", "0" * 64, "manifest hash"),
    ],
)
def test_calibration_identity_and_exact_hashes_are_hard_gates(
    field: str, value: str, message: str
) -> None:
    authority, scope, _, _ = _software_lifecycle_inputs()
    scope = replace(
        scope,
        calibration_reference=replace(scope.calibration_reference, **{field: value}),
    )

    with pytest.raises(ValueError, match=message):
        _validate_calibration_lifecycle(authority, scope)


@pytest.mark.parametrize(
    ("member_change", "message"),
    [
        ({"tone_set_id": "wrong-tones"}, "tone_set_id"),
        ({"stimulus_sha256": "0" * 64}, "stimulus_hash"),
        ({"configuration_id": "WRONG"}, "configuration"),
    ],
)
def test_scope_tone_stimulus_and_configuration_mismatches_are_rejected(
    member_change: dict[str, object], message: str
) -> None:
    authority, scope, source, p2b = _software_lifecycle_inputs()
    scope = replace(scope, members=(replace(scope.members[0], **member_change),))

    with pytest.raises(ValueError, match=message):
        analyze_multisine_hr_readout(
            (source,), scope, p2b, authority, _readout_config("nearest_tone")
        )


def test_p2b_mismatch_and_dense_sweep_feature_are_rejected() -> None:
    authority, scope, source, p2b = _software_lifecycle_inputs()
    wrong_p2b_scope = replace(
        scope, p2b_reference=DatasetQCReference("wrong-scope", _digest("0"))
    )
    with pytest.raises(ValueError, match="P2-B gate failed"):
        analyze_multisine_hr_readout(
            (source,), wrong_p2b_scope, p2b, authority,
            _readout_config("nearest_tone"),
        )

    sweep = _p6a_feature()
    sweep = replace(sweep, sample_id=source.sample_id, meta=replace(
        sweep.meta, sample_id=source.sample_id
    ))
    with pytest.raises(ValueError, match="tone_measurement_from_multisine"):
        analyze_multisine_hr_readout(
            (sweep,), scope, p2b, authority, _readout_config("nearest_tone")
        )


def test_scope_rejects_sealed_final_test_sample() -> None:
    _, scope, _, _ = _software_lifecycle_inputs()
    with pytest.raises(ValueError, match="sealed final-test sample"):
        replace(
            scope,
            final_test_seal=FinalTestSeal(
                True, (scope.members[0].sample_id,), _digest("f")
            ),
        )
