from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from acoustic_encoder.quality_control import (
    MeasurementQCResult,
    QCCheckResult,
    QCScope,
    QCSourceStage,
    evaluate_measurement_quality,
)
from acoustic_encoder.research_gate import ResearchGateError
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
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


def _quality_config() -> dict:
    return {
        "schema_version": "1.0.0",
        "provisional": True,
        "modes": {
            "rew_sweep": {
                "minimum_valid_points": 5,
                "required_frequency_range_hz": [1000, 8000],
                "unavailable_required_check_policy": "warning",
                "phase_policy": "optional",
                "phase_inconsistency_status": "warning",
                "magnitude_db": {
                    "warning_bounds": [-20, 160],
                    "exclude_candidate_bounds": [-100, 220],
                    "warning_dynamic_range_db": 100,
                    "exclude_candidate_dynamic_range_db": 160,
                },
                "required_upstream_checks": [],
            },
            "schroeder_multisine": {
                "minimum_valid_points": 5,
                "required_frequency_range_hz": [1000, 8000],
                "unavailable_required_check_policy": "warning",
                "phase_policy": "upstream_authoritative",
                "phase_inconsistency_status": "exclude_candidate",
                "magnitude_db": {
                    "warning_bounds": [-120, 60],
                    "exclude_candidate_bounds": [-180, 120],
                    "warning_dynamic_range_db": 100,
                    "exclude_candidate_dynamic_range_db": 160,
                },
                "required_upstream_checks": [
                    "p8.aggregate",
                    "p8.clipping",
                    "p8.clock_drift",
                    "p8.non_excited_energy",
                    "p8.tone.snr",
                    "p8.tone.leakage",
                    "p8.tone.period_variance",
                    "p8.tone.missing_tone",
                ],
            },
        },
    }


def _clean_sweep_spectrum() -> SpectrumData:
    meta = MeasurementMeta(
        sample_id="qc-clean-sweep",
        **SCHEMA_VERSION_QUARTET,
        device_version="V2",
        configuration="U4ENC",
        angle_deg=0.0,
        session_id="S01",
        repeat_type="CONT",
        repeat_id="R01",
        experiment_step="DEV_C1",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.MOCK_DENSE,
        source_path="synthetic-clean-sweep.txt",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256="1" * 64,
        provenance_uri="software-validation-fixture",
        eligible_for_scientific_analysis=False,
    )
    return SpectrumData(
        frequency_hz=np.arange(1000.0, 8000.0 + 1000.0, 1000.0),
        magnitude_db=np.arange(70.0, 78.0),
        valid_mask=np.ones(8, dtype=bool),
        representation=Representation.DENSE_SPECTRUM,
        phase_status=PhaseStatus.UNAVAILABLE,
        quality_metrics={},
        magnitude_quantity="spl",
        meta=meta,
    )


def _clean_multisine_spectrum() -> SpectrumData:
    sweep = _clean_sweep_spectrum()
    meta = replace(
        sweep.meta,
        sample_id="qc-clean-multisine",
        measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        source_format=SourceFormat.MOCK_AUDIO,
        source_path="synthetic-clean-recording.wav",
        source_sha256="2" * 64,
        stimulus_id="stimulus-fixture",
        stimulus_hash="3" * 64,
        tone_set_id="tone-set-fixture",
        sidecar_path="synthetic-clean-recording.json",
        audio_channel=0,
    )
    tone_quality = []
    for frequency in sweep.frequency_hz:
        tone_quality.append(
            {
                "frequency_hz": float(frequency),
                "snr_db": 60.0,
                "snr_status": "valid",
                "snr_method": "median_local_non_excited_bin_power",
                "snr_noise_bin_count": 6,
                "leakage_ratio": 1.0e-6,
                "leakage_status": "valid",
                "leakage_method": (
                    "local_non_excited_bin_energy_over_tone_bin_energy"
                ),
                "leakage_bin_count": 4,
                "leakage_guard_bins": 1,
                "leakage_radius_bins": 3,
                "period_variance": 1.0e-8,
                "period_variance_status": "valid",
                "period_variance_method": "complex_relative_variance",
                "magnitude_variance_db2": 0.0,
                "phase_circular_variance": 0.0,
                "period_count": 8,
                "missing_tone": False,
                "valid_tone": True,
                "qc_status": "valid",
                "qc_reasons": [],
            }
        )
    clipping = {
        "status": "valid",
        "sample_count": 0,
        "fraction": 0.0,
        "channel": 0,
        "sample_format": "float32",
        "warning_fraction": 0.001,
        "exclude_candidate_fraction": 0.01,
    }
    clock_drift = {
        "final_decision": "valid",
        "warning_ppm": 20.0,
        "exclude_candidate_ppm": 100.0,
        "correction_mode": "disabled",
        "pre_correction": {"signed_drift_ppm": 0.0},
        "residual": None,
    }
    non_excited = {
        "status": "valid",
        "energy_ratio": 1.0e-7,
        "bin_count": 100,
        "guard_bins": 1,
        "method": "non_excited_bin_energy_over_total_non_dc_energy",
    }
    p8_qc = {
        "qc_schema_version": "1.0.0",
        "status": "valid",
        "clipping": clipping,
        "missing_tone_count": 0,
        "missing_tone_unavailable_count": 0,
        "valid_tone_count": len(tone_quality),
        "warning_tone_count": 0,
        "exclude_candidate_tone_count": 0,
        "non_excited_energy": non_excited,
        "unavailable_items": [],
    }
    return SpectrumData(
        frequency_hz=sweep.frequency_hz,
        magnitude_db=np.zeros(8),
        magnitude_linear=np.ones(8),
        valid_mask=np.ones(8, dtype=bool),
        representation=Representation.SPARSE_TONES,
        phase_status=PhaseStatus.RELATIVE_UNRELIABLE,
        phase_rad=np.zeros(8),
        quality_metrics={
            "p8_qc": p8_qc,
            "tone_quality": tone_quality,
            "clipping": clipping,
            "clock_drift": clock_drift,
            "missing_tones": {"count": 0, "unavailable_count": 0},
            "non_excited_energy": non_excited,
        },
        magnitude_quantity="transfer_gain",
        magnitude_reference="stimulus_tone",
        meta=meta,
    )
def test_clean_sweep_produces_valid_typed_measurement_qc() -> None:
    spectrum = _clean_sweep_spectrum()

    result = evaluate_measurement_quality(
        spectrum,
        _quality_config(),
        run_purpose="software_validation",
    )

    assert isinstance(result, MeasurementQCResult)
    assert result.sample_id == spectrum.meta.sample_id
    assert result.measurement_mode is MeasurementMode.REW_SWEEP
    assert result.aggregate_status is QCStatus.VALID
    assert result.eligible_for_downstream is True
    assert {check.check_id for check in result.checks} >= {
        "p2.metadata.required_fields",
        "p2.metadata.mode_fields",
        "p2.provenance.integrity",
        "p2.spectrum.schema_invariants",
        "p2.spectrum.valid_point_count",
        "p2.spectrum.frequency_coverage",
        "p2.spectrum.magnitude_bounds",
        "p2.phase.consistency",
    }


def test_nonfinite_phase_at_valid_points_is_audited_without_mutation() -> None:
    spectrum = _clean_multisine_spectrum()
    phase = np.array(spectrum.phase_rad, copy=True)
    phase[3] = np.nan

    result = evaluate_measurement_quality(
        replace(spectrum, phase_rad=phase),
        _quality_config(),
        run_purpose="software_validation",
    )

    check = next(
        check for check in result.checks if check.check_id == "p2.phase.finite"
    )
    assert check.status is QCCheckStatus.EXCLUDE_CANDIDATE
    assert check.measured_value == 7
    assert np.isnan(phase[3])


def test_aggregation_is_order_independent_and_preserves_every_failure_reason() -> None:
    upstream = (
        QCCheckResult(
            check_id="p1.warning",
            scope=QCScope.MEASUREMENT,
            status=QCCheckStatus.WARNING,
            source_stage=QCSourceStage.P1,
            source_module="test.adapter",
            reason="adapter_warning",
        ),
        QCCheckResult(
            check_id="p8.exclude",
            scope=QCScope.MEASUREMENT,
            status=QCCheckStatus.EXCLUDE_CANDIDATE,
            source_stage=QCSourceStage.P8,
            source_module="test.p8",
            reason="p8_exclude",
        ),
    )

    forward = evaluate_measurement_quality(
        _clean_sweep_spectrum(),
        _quality_config(),
        run_purpose="software_validation",
        upstream_checks=upstream,
    )
    reverse = evaluate_measurement_quality(
        _clean_sweep_spectrum(),
        _quality_config(),
        run_purpose="software_validation",
        upstream_checks=tuple(reversed(upstream)),
    )

    assert forward.aggregate_status is QCStatus.EXCLUDE_CANDIDATE
    assert reverse.aggregate_status is QCStatus.EXCLUDE_CANDIDATE
    assert forward.warning_reasons == ("adapter_warning",)
    assert forward.exclude_candidate_reasons == ("p8_exclude",)


def test_adapter_reported_qc_status_is_preserved_without_changing_human_valid() -> None:
    spectrum = _clean_sweep_spectrum()
    adapter_meta = replace(spectrum.meta, qc_status=QCStatus.WARNING)

    result = evaluate_measurement_quality(
        replace(spectrum, meta=adapter_meta),
        _quality_config(),
        run_purpose="software_validation",
    )

    adapter_check = next(
        check for check in result.checks if check.check_id == "p1.adapter.aggregate"
    )
    assert adapter_check.status is QCCheckStatus.WARNING
    assert result.aggregate_status is QCStatus.WARNING
    assert result.human_valid is True
    assert adapter_meta.valid is True


def test_required_unavailable_is_preserved_and_promoted_only_by_policy() -> None:
    unavailable = QCCheckResult(
        check_id="p8.required_metric",
        scope=QCScope.MEASUREMENT,
        status=QCCheckStatus.UNAVAILABLE,
        source_stage=QCSourceStage.P8,
        source_module="test.p8",
        reason="metric_not_available",
        required=True,
    )
    warning_config = _quality_config()
    preserve_config = _quality_config()
    preserve_config["modes"]["rew_sweep"][
        "unavailable_required_check_policy"
    ] = "preserve"

    warning = evaluate_measurement_quality(
        _clean_sweep_spectrum(),
        warning_config,
        run_purpose="software_validation",
        upstream_checks=(unavailable,),
    )
    preserved = evaluate_measurement_quality(
        _clean_sweep_spectrum(),
        preserve_config,
        run_purpose="software_validation",
        upstream_checks=(unavailable,),
    )

    assert warning.aggregate_status is QCStatus.WARNING
    assert preserved.aggregate_status is QCStatus.VALID
    assert "p8.required_metric" in warning.unavailable_checks
    assert "metric_not_available" in warning.warning_reasons
    assert warning.checks[-1].status is QCCheckStatus.UNAVAILABLE
    assert warning.checks[-1].available is False


def test_manual_review_and_human_invalid_are_separate_from_automatic_qc() -> None:
    spectrum = _clean_sweep_spectrum()
    human_meta = replace(
        spectrum.meta,
        valid=False,
        exclusion_reason="operator_rejected_setup",
        manual_review_reasons=("confirm_microphone_channel",),
    )
    human_spectrum = replace(spectrum, meta=human_meta)

    result = evaluate_measurement_quality(
        human_spectrum,
        _quality_config(),
        run_purpose="software_validation",
    )

    assert result.aggregate_status is QCStatus.VALID
    assert result.human_valid is False
    assert result.human_exclusion_reason == "operator_rejected_setup"
    assert result.manual_review_reasons == ("confirm_microphone_channel",)
    assert result.eligible_for_downstream is False
    assert human_spectrum.meta == human_meta


def test_rew_unavailable_evidence_is_preserved_as_optional_p1_checks() -> None:
    spectrum = replace(
        _clean_sweep_spectrum(),
        quality_metrics={
            "headroom": "unavailable",
            "noise_floor": "unavailable",
            "raw_waveform": "unavailable",
            "impulse_response": "unavailable",
            "window": "unavailable",
        },
    )

    result = evaluate_measurement_quality(
        spectrum,
        _quality_config(),
        run_purpose="software_validation",
    )

    rew_checks = {
        check.check_id: check
        for check in result.checks
        if check.check_id.startswith("p1.rew.")
    }
    assert set(rew_checks) == {
        "p1.rew.headroom",
        "p1.rew.noise_floor",
        "p1.rew.raw_waveform",
        "p1.rew.impulse_response",
        "p1.rew.window",
    }
    assert all(check.status is QCCheckStatus.UNAVAILABLE for check in rew_checks.values())
    assert all(check.required is False for check in rew_checks.values())
    assert result.aggregate_status is QCStatus.VALID


def test_missing_phase_is_unavailable_when_optional_and_warning_when_required() -> None:
    optional_config = _quality_config()
    required_config = _quality_config()
    required_config["modes"]["rew_sweep"]["phase_policy"] = "required_warning"

    optional = evaluate_measurement_quality(
        _clean_sweep_spectrum(),
        optional_config,
        run_purpose="software_validation",
    )
    required = evaluate_measurement_quality(
        _clean_sweep_spectrum(),
        required_config,
        run_purpose="software_validation",
    )

    optional_check = next(
        check for check in optional.checks if check.check_id == "p2.phase.availability"
    )
    required_check = next(
        check for check in required.checks if check.check_id == "p2.phase.availability"
    )
    assert optional_check.status is QCCheckStatus.UNAVAILABLE
    assert optional_check.required is False
    assert optional.aggregate_status is QCStatus.VALID
    assert required_check.status is QCCheckStatus.WARNING
    assert required_check.required is True
    assert required.aggregate_status is QCStatus.WARNING


def test_frequency_coverage_shortfall_is_a_warning_without_deleting_points() -> None:
    spectrum = _clean_sweep_spectrum()
    shifted = replace(spectrum, frequency_hz=spectrum.frequency_hz + 1000.0)

    result = evaluate_measurement_quality(
        shifted,
        _quality_config(),
        run_purpose="software_validation",
    )

    coverage = next(
        check for check in result.checks if check.check_id == "p2.spectrum.frequency_coverage"
    )
    assert coverage.status is QCCheckStatus.WARNING
    assert coverage.reason == "required_frequency_range_not_covered"
    assert result.aggregate_status is QCStatus.WARNING
    np.testing.assert_array_equal(shifted.valid_mask, np.ones(8, dtype=bool))


def test_insufficient_valid_points_are_an_exclude_candidate_only() -> None:
    spectrum = _clean_sweep_spectrum()
    mask = np.array([True, True, True, True, False, False, False, False])
    sparse_validity = replace(spectrum, valid_mask=mask)

    result = evaluate_measurement_quality(
        sparse_validity,
        _quality_config(),
        run_purpose="software_validation",
    )

    point_check = next(
        check for check in result.checks if check.check_id == "p2.spectrum.valid_point_count"
    )
    assert point_check.measured_value == 4
    assert point_check.status is QCCheckStatus.EXCLUDE_CANDIDATE
    assert result.aggregate_status is QCStatus.EXCLUDE_CANDIDATE
    np.testing.assert_array_equal(sparse_validity.valid_mask, mask)


def test_magnitude_bounds_distinguish_warning_from_exclude_candidate() -> None:
    spectrum = _clean_sweep_spectrum()
    warning_values = np.array(spectrum.magnitude_db, copy=True)
    warning_values[0] = -30.0
    exclude_values = np.array(spectrum.magnitude_db, copy=True)
    exclude_values[0] = -120.0

    warning = evaluate_measurement_quality(
        replace(spectrum, magnitude_db=warning_values),
        _quality_config(),
        run_purpose="software_validation",
    )
    excluded = evaluate_measurement_quality(
        replace(spectrum, magnitude_db=exclude_values),
        _quality_config(),
        run_purpose="software_validation",
    )

    warning_check = next(
        check for check in warning.checks if check.check_id == "p2.spectrum.magnitude_bounds"
    )
    exclude_check = next(
        check for check in excluded.checks if check.check_id == "p2.spectrum.magnitude_bounds"
    )
    assert warning_check.status is QCCheckStatus.WARNING
    assert warning.aggregate_status is QCStatus.WARNING
    assert exclude_check.status is QCCheckStatus.EXCLUDE_CANDIDATE
    assert excluded.aggregate_status is QCStatus.EXCLUDE_CANDIDATE


def test_schema_version_mismatch_is_audited_as_exclude_candidate() -> None:
    spectrum = _clean_sweep_spectrum()
    old_meta = replace(
        spectrum.meta,
        pipeline_version="1.9.0",
        config_schema_version="1.0.0",
    )

    result = evaluate_measurement_quality(
        replace(spectrum, meta=old_meta),
        _quality_config(),
        run_purpose="software_validation",
    )

    compatibility = next(
        check for check in result.checks if check.check_id == "p2.schema.compatibility"
    )
    assert compatibility.status is QCCheckStatus.EXCLUDE_CANDIDATE
    assert compatibility.reason == "unsupported_schema_or_pipeline_version"
    assert result.aggregate_status is QCStatus.EXCLUDE_CANDIDATE


def test_p2_reuses_the_research_hard_gate() -> None:
    with pytest.raises(ResearchGateError, match="real_experiment"):
        evaluate_measurement_quality(
            _clean_sweep_spectrum(),
            _quality_config(),
            run_purpose="research_analysis",
        )


def test_multisine_reuses_p8_measurement_and_per_tone_evidence() -> None:
    result = evaluate_measurement_quality(
        _clean_multisine_spectrum(),
        _quality_config(),
        run_purpose="software_validation",
    )

    p8_checks = [
        check for check in result.checks if check.source_stage is QCSourceStage.P8
    ]
    assert result.aggregate_status is QCStatus.VALID
    assert {check.check_id for check in p8_checks} >= {
        "p8.aggregate",
        "p8.clipping",
        "p8.clock_drift",
        "p8.non_excited_energy",
        "p8.tone.snr",
        "p8.tone.leakage",
        "p8.tone.period_variance",
        "p8.tone.missing_tone",
    }
    assert sum(check.check_id == "p8.tone.snr" for check in p8_checks) == 8
    tone_check = next(
        check for check in p8_checks if check.check_id == "p8.tone.snr"
    )
    assert tone_check.scope is QCScope.TONE
    assert tone_check.frequency_hz == 1000.0
    assert tone_check.source_module == "acoustic_encoder.multisine_qc"


def test_p8_warning_exclude_and_tone_reasons_are_preserved_together() -> None:
    spectrum = _clean_multisine_spectrum()
    metrics = deepcopy(spectrum.quality_metrics)
    metrics["p8_qc"]["status"] = "exclude_candidate"
    metrics["p8_qc"]["warning_tone_count"] = 1
    metrics["p8_qc"]["exclude_candidate_tone_count"] = 1
    metrics["clipping"]["status"] = "warning"
    metrics["tone_quality"][0]["snr_status"] = "warning"
    metrics["tone_quality"][0]["leakage_status"] = "exclude_candidate"
    metrics["tone_quality"][0]["qc_status"] = "exclude_candidate"
    metrics["tone_quality"][0]["valid_tone"] = False
    metrics["tone_quality"][0]["qc_reasons"] = [
        "snr_warning",
        "leakage_exclude_candidate",
    ]

    result = evaluate_measurement_quality(
        replace(spectrum, quality_metrics=metrics),
        _quality_config(),
        run_purpose="software_validation",
    )

    tone = [
        check
        for check in result.checks
        if check.frequency_hz == 1000.0 and check.source_stage is QCSourceStage.P8
    ]
    assert result.aggregate_status is QCStatus.EXCLUDE_CANDIDATE
    assert {check.status for check in tone} >= {
        QCCheckStatus.WARNING,
        QCCheckStatus.EXCLUDE_CANDIDATE,
    }
    assert all(
        check.details["qc_reasons"]
        == ["snr_warning", "leakage_exclude_candidate"]
        for check in tone
    )
    assert any("p8_clipping_warning" == reason for reason in result.warning_reasons)
    assert len(result.exclude_candidate_reasons) >= 2
