from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from acoustic_encoder.config import load_config
from acoustic_encoder.io_multisine import (
    MultisineClockDriftError,
    MultisineConsistencyError,
    MultisineImportError,
    MultisineSynchronizationError,
    load_multisine_measurement,
)
from acoustic_encoder.mock_data import generate_dual_mode_mock, known_transfer_db
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import (
    DataOrigin,
    MeasurementMeta,
    PhaseStatus,
    Representation,
    artifact_sha256,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAGNITUDE_TOLERANCE_DB = 0.05


def simulated_case(
    tmp_path,
    *,
    include_preamble: bool = True,
    sampling_clock_drift_ppm: float = 0.0,
    stable_period_count: int | None = None,
):
    resolved = load_config(
        PROJECT_ROOT / "config" / "stimulus_multisine_broadband.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    stimulus = deepcopy(resolved["stimulus"])
    if not include_preamble:
        stimulus["preamble"] = {"type": "none"}
    if stable_period_count is not None:
        stimulus["stable_period_count"] = stable_period_count
    delay_samples = 1379
    mock_manifest_path = generate_dual_mode_mock(
        tmp_path,
        stimulus,
        configurations=["U4ENC"],
        angles_deg=[0],
        random_state=123,
        recording_delay_samples=delay_samples,
        sampling_clock_drift_ppm=sampling_clock_drift_ppm,
    )
    mock_manifest = json.loads(mock_manifest_path.read_text(encoding="utf-8"))
    meta = MeasurementMeta.from_dict(
        next(
            sample
            for sample in mock_manifest["samples"]
            if sample["measurement_mode"] == "schroeder_multisine"
        )
    )
    stimulus_manifest_path = Path(mock_manifest["stimulus_manifest"])
    return stimulus, delay_samples, meta, stimulus_manifest_path


def _clock_drift_config(*, correction: str) -> dict[str, float | str]:
    return {
        "warning_ppm": 20.0,
        "exclude_candidate_ppm": 100.0,
        "correction": correction,
    }


def test_simulated_multisine_recovers_known_transfer_after_nonperiod_delay(
    tmp_path,
) -> None:
    stimulus, delay_samples, meta, stimulus_manifest_path = simulated_case(tmp_path)

    spectrum = load_multisine_measurement(
        meta.source_path,
        stimulus_manifest_path,
        meta,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        period_averaging="complex_spectrum",
    )

    expected_db = known_transfer_db(
        spectrum.frequency_hz,
        angle_deg=meta.angle_deg,
        configuration=meta.configuration,
    )
    assert spectrum.representation is Representation.SPARSE_TONES
    assert spectrum.phase_status is PhaseStatus.RELATIVE_UNRELIABLE
    assert spectrum.meta.data_origin is DataOrigin.SIMULATED
    assert spectrum.quality_metrics["preamble_start_sample"] == (
        delay_samples + round(stimulus["pre_silence_s"] * stimulus["sample_rate_hz"])
    )
    assert np.max(np.abs(spectrum.magnitude_db - expected_db)) <= MAGNITUDE_TOLERANCE_DB


def test_clock_drift_disabled_warns_without_upgrading_phase(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(
        tmp_path,
        sampling_clock_drift_ppm=50.0,
    )

    spectrum = load_multisine_measurement(
        meta.source_path,
        stimulus_manifest_path,
        meta,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        period_averaging="complex_spectrum",
        clock_drift_config=_clock_drift_config(correction="disabled"),
    )

    drift_qc = spectrum.quality_metrics["clock_drift"]
    assert drift_qc["pre_correction"]["signed_drift_ppm"] == pytest.approx(
        50.0,
        abs=1.0,
    )
    assert drift_qc["pre_correction"]["decision"] == "warning"
    assert drift_qc["correction"]["applied"] is False
    assert drift_qc["final_decision"] == "warning"
    assert spectrum.phase_status is PhaseStatus.RELATIVE_UNRELIABLE


def test_zero_clock_drift_is_estimated_as_valid(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(tmp_path)

    spectrum = load_multisine_measurement(
        meta.source_path,
        stimulus_manifest_path,
        meta,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        period_averaging="complex_spectrum",
        clock_drift_config=_clock_drift_config(correction="disabled"),
    )

    pre = spectrum.quality_metrics["clock_drift"]["pre_correction"]
    assert pre["signed_drift_ppm"] == pytest.approx(0.0, abs=1.0)
    assert pre["decision"] == "valid"
    assert spectrum.phase_status is PhaseStatus.RELATIVE_UNRELIABLE


@pytest.mark.parametrize(
    ("sampling_clock_drift_ppm", "expected_decision"),
    [(10.0, "valid"), (120.0, "exclude_candidate")],
)
def test_clock_drift_disabled_applies_configured_decision_without_correction(
    tmp_path,
    sampling_clock_drift_ppm: float,
    expected_decision: str,
) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(
        tmp_path,
        sampling_clock_drift_ppm=sampling_clock_drift_ppm,
    )

    spectrum = load_multisine_measurement(
        meta.source_path,
        stimulus_manifest_path,
        meta,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        period_averaging="complex_spectrum",
        clock_drift_config=_clock_drift_config(correction="disabled"),
    )

    drift_qc = spectrum.quality_metrics["clock_drift"]
    assert drift_qc["pre_correction"]["decision"] == expected_decision
    assert drift_qc["final_decision"] == expected_decision
    assert drift_qc["correction"]["applied"] is False
    assert spectrum.phase_status is PhaseStatus.RELATIVE_UNRELIABLE
    assert spectrum.phase_status is not PhaseStatus.COMMON_CLOCK


def test_clock_drift_enabled_corrects_and_reestimates_tone_transfer(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(
        tmp_path,
        sampling_clock_drift_ppm=80.0,
    )

    spectrum = load_multisine_measurement(
        meta.source_path,
        stimulus_manifest_path,
        meta,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        period_averaging="complex_spectrum",
        clock_drift_config=_clock_drift_config(correction="enabled"),
    )

    expected_db = known_transfer_db(
        spectrum.frequency_hz,
        angle_deg=meta.angle_deg,
        configuration=meta.configuration,
    )
    drift_qc = spectrum.quality_metrics["clock_drift"]
    assert drift_qc["pre_correction"]["signed_drift_ppm"] == pytest.approx(
        80.0,
        abs=1.0,
    )
    assert drift_qc["correction"]["applied"] is True
    assert drift_qc["correction"]["successful"] is True
    assert drift_qc["correction"]["method"] == (
        "quintic_spline_time_axis_resampling"
    )
    assert drift_qc["correction"]["ratio"] == pytest.approx(
        1.0 / (1.0 + drift_qc["pre_correction"]["signed_drift_ppm"] * 1.0e-6),
    )
    assert abs(drift_qc["post_correction"]["signed_residual_drift_ppm"]) <= 1.0
    assert drift_qc["post_correction"]["decision"] == "valid"
    assert drift_qc["final_decision"] == "valid"
    assert spectrum.phase_status is PhaseStatus.DRIFT_CORRECTED
    assert np.max(np.abs(spectrum.magnitude_db - expected_db)) <= MAGNITUDE_TOLERANCE_DB


def test_clock_drift_enabled_corrects_negative_drift(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(
        tmp_path,
        sampling_clock_drift_ppm=-80.0,
    )

    spectrum = load_multisine_measurement(
        meta.source_path,
        stimulus_manifest_path,
        meta,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        period_averaging="complex_spectrum",
        clock_drift_config=_clock_drift_config(correction="enabled"),
    )

    expected_db = known_transfer_db(
        spectrum.frequency_hz,
        angle_deg=meta.angle_deg,
        configuration=meta.configuration,
    )
    drift_qc = spectrum.quality_metrics["clock_drift"]
    assert drift_qc["pre_correction"]["signed_drift_ppm"] == pytest.approx(
        -80.0,
        abs=1.0,
    )
    assert abs(drift_qc["post_correction"]["signed_residual_drift_ppm"]) <= 1.0
    assert drift_qc["correction"]["successful"] is True
    assert spectrum.phase_status is PhaseStatus.DRIFT_CORRECTED
    assert np.max(np.abs(spectrum.magnitude_db - expected_db)) <= MAGNITUDE_TOLERANCE_DB


def test_clock_correction_does_not_claim_phase_for_power_averaging(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(
        tmp_path,
        sampling_clock_drift_ppm=50.0,
    )

    spectrum = load_multisine_measurement(
        meta.source_path,
        stimulus_manifest_path,
        meta,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        period_averaging="power",
        clock_drift_config=_clock_drift_config(correction="enabled"),
    )

    assert spectrum.quality_metrics["clock_drift"]["correction"]["successful"] is True
    assert spectrum.phase_rad is None
    assert spectrum.phase_status is PhaseStatus.RELATIVE_UNRELIABLE
    assert spectrum.phase_status is not PhaseStatus.COMMON_CLOCK


def test_clock_correction_keeps_phase_unreliable_when_residual_qc_fails(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(
        tmp_path,
        sampling_clock_drift_ppm=80.0,
    )

    spectrum = load_multisine_measurement(
        meta.source_path,
        stimulus_manifest_path,
        meta,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        period_averaging="complex_spectrum",
        clock_drift_config={
            "warning_ppm": 1.0e-9,
            "exclude_candidate_ppm": 0.1,
            "correction": "enabled",
        },
    )

    drift_qc = spectrum.quality_metrics["clock_drift"]
    assert drift_qc["correction"]["applied"] is True
    assert drift_qc["correction"]["successful"] is False
    assert drift_qc["post_correction"]["decision"] in {
        "warning",
        "exclude_candidate",
    }
    assert drift_qc["correction"]["failure_reason"] == (
        "residual_drift_not_below_warning_threshold"
    )
    assert spectrum.phase_status is PhaseStatus.RELATIVE_UNRELIABLE
    assert spectrum.phase_status is not PhaseStatus.COMMON_CLOCK


def test_clock_drift_estimation_fails_explicitly_with_one_stable_period(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(
        tmp_path,
        stable_period_count=1,
    )

    with pytest.raises(MultisineClockDriftError, match="at least two complete periods"):
        load_multisine_measurement(
            meta.source_path,
            stimulus_manifest_path,
            meta,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
            period_averaging="complex_spectrum",
            clock_drift_config=_clock_drift_config(correction="disabled"),
        )


def test_power_period_averaging_recovers_magnitude_without_claiming_phase(
    tmp_path,
) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(tmp_path)

    spectrum = load_multisine_measurement(
        meta.source_path,
        stimulus_manifest_path,
        meta,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        period_averaging="power",
    )

    expected_db = known_transfer_db(
        spectrum.frequency_hz,
        angle_deg=meta.angle_deg,
        configuration=meta.configuration,
    )
    assert spectrum.phase_rad is None
    assert spectrum.phase_status is PhaseStatus.RELATIVE_UNRELIABLE
    assert spectrum.quality_metrics["period_averaging"] == "power"
    assert np.max(np.abs(spectrum.magnitude_db - expected_db)) <= MAGNITUDE_TOLERANCE_DB


def test_multisine_rejects_sidecar_period_length_mismatch(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(tmp_path)
    sidecar_path = Path(meta.sidecar_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["period_samples"] += 1
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(MultisineConsistencyError, match="period_samples"):
        load_multisine_measurement(
            meta.source_path,
            stimulus_manifest_path,
            meta,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
            period_averaging="complex_spectrum",
        )


def test_multisine_rejects_sidecar_sample_rate_mismatch(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(tmp_path)
    sidecar_path = Path(meta.sidecar_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["sample_rate_hz"] = 44100
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(MultisineConsistencyError, match="sample rate"):
        load_multisine_measurement(
            meta.source_path,
            stimulus_manifest_path,
            meta,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
            period_averaging="complex_spectrum",
        )


def test_multisine_rejects_recording_wav_sample_rate_mismatch(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(tmp_path)
    recording_path = Path(meta.source_path)
    _, recording = wavfile.read(recording_path)
    wavfile.write(recording_path, 44100, recording)
    recording_hash = artifact_sha256(recording_path)
    sidecar_path = Path(meta.sidecar_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["recording_sha256"] = recording_hash
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    meta = replace(meta, source_sha256=recording_hash)

    with pytest.raises(MultisineConsistencyError, match="sample rate"):
        load_multisine_measurement(
            recording_path,
            stimulus_manifest_path,
            meta,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
            period_averaging="complex_spectrum",
        )


def test_multisine_rejects_sidecar_tone_set_mismatch(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(tmp_path)
    sidecar_path = Path(meta.sidecar_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["tone_set_id"] = "different-tone-set"
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(MultisineConsistencyError, match="tone_set_id"):
        load_multisine_measurement(
            meta.source_path,
            stimulus_manifest_path,
            meta,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
            period_averaging="complex_spectrum",
        )


def test_multisine_rejects_sidecar_stimulus_hash_mismatch(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(tmp_path)
    sidecar_path = Path(meta.sidecar_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["stimulus_hash"] = "0" * 64
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(MultisineConsistencyError, match="stimulus hash"):
        load_multisine_measurement(
            meta.source_path,
            stimulus_manifest_path,
            meta,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
            period_averaging="complex_spectrum",
        )


def test_multisine_rejects_modified_stimulus_wav(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(tmp_path)
    manifest = json.loads(stimulus_manifest_path.read_text(encoding="utf-8"))
    stimulus_path = stimulus_manifest_path.parent / manifest["wav_file"]
    stimulus_path.write_bytes(stimulus_path.read_bytes() + b"\x00")

    with pytest.raises(MultisineConsistencyError, match="stimulus hash"):
        load_multisine_measurement(
            meta.source_path,
            stimulus_manifest_path,
            meta,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
            period_averaging="complex_spectrum",
        )


def test_multisine_rejects_sidecar_recording_hash_mismatch(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(tmp_path)
    sidecar_path = Path(meta.sidecar_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["recording_sha256"] = "0" * 64
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(MultisineConsistencyError, match="recording hash"):
        load_multisine_measurement(
            meta.source_path,
            stimulus_manifest_path,
            meta,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
            period_averaging="complex_spectrum",
        )


def test_multisine_rejects_internally_inconsistent_manifest_period(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(tmp_path)
    manifest = json.loads(stimulus_manifest_path.read_text(encoding="utf-8"))
    manifest["period_samples"] += 1
    stimulus_manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    sidecar_path = Path(meta.sidecar_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["period_samples"] = manifest["period_samples"]
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(MultisineConsistencyError, match="manifest period"):
        load_multisine_measurement(
            meta.source_path,
            stimulus_manifest_path,
            meta,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
            period_averaging="complex_spectrum",
        )


def test_p8a_marks_deferred_multisine_qc_unavailable(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(tmp_path)

    spectrum = load_multisine_measurement(
        meta.source_path,
        stimulus_manifest_path,
        meta,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        period_averaging="complex_spectrum",
    )

    assert spectrum.quality_metrics["clock_drift"] == "unavailable"
    assert spectrum.quality_metrics["missing_tones"] == "unavailable"
    assert spectrum.quality_metrics["clipping"] == "unavailable"
    assert spectrum.quality_metrics["leakage"] == "unavailable"


def test_multisine_rejects_incomplete_stable_period(tmp_path) -> None:
    stimulus, delay_samples, meta, stimulus_manifest_path = simulated_case(tmp_path)
    manifest = json.loads(stimulus_manifest_path.read_text(encoding="utf-8"))
    recording_path = Path(meta.source_path)
    sample_rate, recording = wavfile.read(recording_path)
    first_period_start = (
        delay_samples
        + round(stimulus["pre_silence_s"] * sample_rate)
        + manifest["preamble_samples"]
        + manifest["preamble_gap_samples"]
    )
    analysis_start = (
        first_period_start
        + manifest["discard_initial_period_count"] * manifest["period_samples"]
    )
    incomplete_stop = (
        analysis_start
        + manifest["stable_period_count"] * manifest["period_samples"]
        - 1
    )
    wavfile.write(recording_path, sample_rate, recording[:incomplete_stop])
    recording_hash = artifact_sha256(recording_path)
    sidecar_path = Path(meta.sidecar_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["recording_sha256"] = recording_hash
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    meta = replace(meta, source_sha256=recording_hash)

    with pytest.raises(MultisineSynchronizationError, match="complete stable periods"):
        load_multisine_measurement(
            recording_path,
            stimulus_manifest_path,
            meta,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
            period_averaging="complex_spectrum",
        )


def test_multisine_excludes_manifest_discard_periods_from_transfer(tmp_path) -> None:
    stimulus, delay_samples, meta, stimulus_manifest_path = simulated_case(tmp_path)
    manifest = json.loads(stimulus_manifest_path.read_text(encoding="utf-8"))
    recording_path = Path(meta.source_path)
    sample_rate, recording = wavfile.read(recording_path)
    first_period_start = (
        delay_samples
        + round(stimulus["pre_silence_s"] * sample_rate)
        + manifest["preamble_samples"]
        + manifest["preamble_gap_samples"]
    )
    discard_stop = (
        first_period_start
        + manifest["discard_initial_period_count"] * manifest["period_samples"]
    )
    recording[first_period_start:discard_stop] *= 5.0
    wavfile.write(recording_path, sample_rate, recording)
    recording_hash = artifact_sha256(recording_path)
    sidecar_path = Path(meta.sidecar_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["recording_sha256"] = recording_hash
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    meta = replace(meta, source_sha256=recording_hash)

    spectrum = load_multisine_measurement(
        recording_path,
        stimulus_manifest_path,
        meta,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        period_averaging="complex_spectrum",
    )

    expected_db = known_transfer_db(
        spectrum.frequency_hz,
        angle_deg=meta.angle_deg,
        configuration=meta.configuration,
    )
    assert spectrum.quality_metrics["discarded_period_count"] == 2
    assert spectrum.quality_metrics["analysis_start_sample"] == discard_stop
    assert np.max(np.abs(spectrum.magnitude_db - expected_db)) <= MAGNITUDE_TOLERANCE_DB


def test_multisine_output_contains_only_manifest_tones(tmp_path) -> None:
    stimulus, _, meta, stimulus_manifest_path = simulated_case(tmp_path)

    spectrum = load_multisine_measurement(
        meta.source_path,
        stimulus_manifest_path,
        meta,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        period_averaging="complex_spectrum",
    )

    tones = stimulus["tones"]
    expected_frequency = np.arange(
        tones["start_hz"],
        tones["stop_hz"] + 0.5 * tones["spacing_hz"],
        tones["spacing_hz"],
    )
    assert spectrum.representation is Representation.SPARSE_TONES
    np.testing.assert_array_equal(spectrum.frequency_hz, expected_frequency)


def test_p8a_rejects_research_analysis_even_for_schema_valid_input(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(tmp_path)

    with pytest.raises(MultisineImportError, match="simulated.*software_validation"):
        load_multisine_measurement(
            meta.source_path,
            stimulus_manifest_path,
            meta,
            run_purpose=RunPurpose.RESEARCH_ANALYSIS,
            period_averaging="complex_spectrum",
        )


def test_p8a_requires_known_preamble_for_synchronization(tmp_path) -> None:
    _, _, meta, stimulus_manifest_path = simulated_case(
        tmp_path,
        include_preamble=False,
    )

    with pytest.raises(MultisineSynchronizationError, match="known preamble"):
        load_multisine_measurement(
            meta.source_path,
            stimulus_manifest_path,
            meta,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
            period_averaging="complex_spectrum",
        )
