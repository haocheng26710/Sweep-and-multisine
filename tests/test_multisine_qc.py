from __future__ import annotations

from copy import deepcopy
import csv
import json
from pathlib import Path

import numpy as np
import pytest

from acoustic_encoder.config import load_config
from acoustic_encoder.io_multisine import analyze_multisine_measurement
from acoustic_encoder.mock_data import generate_dual_mode_mock
from acoustic_encoder.multisine_estimation import PeriodTransferEstimate
from acoustic_encoder.multisine_qc import (
    analyze_clipping,
    evaluate_tone_and_audio_quality,
)
from acoustic_encoder.multisine_outputs import write_multisine_qc_outputs
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import DataOrigin, MeasurementMeta, load_spectrum

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _quality_config() -> dict:
    resolved = load_config(
        PROJECT_ROOT / "config" / "experiment_v2_u4_multisine.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    return deepcopy(resolved["multisine_estimation"]["tone_quality"])


def _simulated_case(tmp_path, **mock_options):
    resolved = load_config(
        PROJECT_ROOT / "config" / "stimulus_multisine_broadband.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    stimulus = deepcopy(resolved["stimulus"])
    mock_manifest_path = generate_dual_mode_mock(
        tmp_path,
        stimulus,
        configurations=["U4ENC"],
        angles_deg=[0],
        random_state=123,
        recording_delay_samples=1379,
        **mock_options,
    )
    mock_manifest = json.loads(mock_manifest_path.read_text(encoding="utf-8"))
    meta = MeasurementMeta.from_dict(
        next(
            sample
            for sample in mock_manifest["samples"]
            if sample["measurement_mode"] == "schroeder_multisine"
        )
    )
    return meta, Path(mock_manifest["stimulus_manifest"])


def _analyze(meta, stimulus_manifest_path, quality_config=None):
    return analyze_multisine_measurement(
        meta.source_path,
        stimulus_manifest_path,
        meta,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        period_averaging="complex_spectrum",
        clock_drift_config={
            "warning_ppm": 20.0,
            "exclude_candidate_ppm": 100.0,
            "correction": "disabled",
        },
        tone_quality_config=quality_config or _quality_config(),
    )


def test_clean_recording_produces_valid_tone_and_measurement_qc(tmp_path) -> None:
    meta, stimulus_manifest_path = _simulated_case(tmp_path)

    analysis = _analyze(meta, stimulus_manifest_path)

    assert analysis.spectrum.meta.data_origin is DataOrigin.SIMULATED
    assert analysis.spectrum.meta.eligible_for_scientific_analysis is False
    assert len(analysis.tone_quality) == 71
    assert all(record.valid_tone for record in analysis.tone_quality)
    assert all(record.snr_status == "valid" for record in analysis.tone_quality)
    assert all(
        record.snr_method == "median_local_non_excited_bin_power"
        for record in analysis.tone_quality
    )
    assert all(record.leakage_status == "valid" for record in analysis.tone_quality)
    assert all(record.leakage_guard_bins == 1 for record in analysis.tone_quality)
    assert all(record.leakage_radius_bins == 3 for record in analysis.tone_quality)
    assert all(record.period_variance_status == "valid" for record in analysis.tone_quality)
    assert all(
        record.period_variance_method == "complex_relative_variance"
        for record in analysis.tone_quality
    )
    assert all(record.missing_tone is False for record in analysis.tone_quality)
    assert analysis.measurement_qc["status"] == "valid"
    assert analysis.measurement_qc["missing_tone_count"] == 0
    assert analysis.measurement_qc["unavailable_items"] == []


@pytest.mark.parametrize(
    ("recording_wav_format", "expected_sample_format"),
    [("float32", "float32"), ("pcm16", "int16")],
)
def test_float_and_integer_pcm_clipping_count_every_sample_and_run(
    tmp_path,
    recording_wav_format: str,
    expected_sample_format: str,
) -> None:
    meta, stimulus_manifest_path = _simulated_case(
        tmp_path,
        recording_wav_format=recording_wav_format,
        clipping_run_samples=16,
    )

    analysis = _analyze(meta, stimulus_manifest_path)

    clipping = analysis.clipping_metrics
    assert clipping["sample_format"] == expected_sample_format
    assert clipping["sample_count"] >= 16
    assert clipping["fraction"] > 0.0
    assert clipping["longest_run_samples"] >= 16
    assert clipping["status"] == "warning"


@pytest.mark.parametrize(
    "missing_frequencies_hz",
    [(1000.0,), (1000.0, 3200.0, 8000.0)],
)
def test_missing_tones_are_retained_and_marked_invalid(
    tmp_path,
    missing_frequencies_hz: tuple[float, ...],
) -> None:
    meta, stimulus_manifest_path = _simulated_case(
        tmp_path,
        missing_tone_frequencies_hz=missing_frequencies_hz,
        additive_noise_std=0.0,
    )

    analysis = _analyze(meta, stimulus_manifest_path)
    by_frequency = {record.frequency_hz: record for record in analysis.tone_quality}

    assert analysis.spectrum.frequency_hz.size == 71
    assert analysis.spectrum.meta.valid is True
    assert analysis.measurement_qc["missing_tone_count"] == len(
        missing_frequencies_hz
    )
    for frequency in missing_frequencies_hz:
        record = by_frequency[frequency]
        assert record.missing_tone is True
        index = int(np.flatnonzero(analysis.spectrum.frequency_hz == frequency)[0])
        assert analysis.spectrum.valid_mask[index] == np.bool_(False)
        assert np.isfinite(analysis.spectrum.magnitude_linear[index])


def test_white_noise_can_exclude_low_snr_without_deleting_tones(tmp_path) -> None:
    meta, stimulus_manifest_path = _simulated_case(
        tmp_path,
        additive_noise_std=1.5e-2,
    )

    analysis = _analyze(meta, stimulus_manifest_path)

    assert any(
        record.snr_status == "exclude_candidate"
        for record in analysis.tone_quality
    )
    assert analysis.measurement_qc["status"] == "exclude_candidate"
    assert analysis.spectrum.frequency_hz.size == 71
    assert analysis.spectrum.meta.valid is True


def test_neighbouring_non_excited_bin_is_tone_leakage_not_another_tone(
    tmp_path,
) -> None:
    meta, stimulus_manifest_path = _simulated_case(
        tmp_path,
        interference_tones_dbfs={1020.0: -60.0},
    )

    analysis = _analyze(meta, stimulus_manifest_path)
    tone = next(record for record in analysis.tone_quality if record.frequency_hz == 1000.0)

    assert tone.leakage_status == "exclude_candidate"
    assert tone.leakage_ratio is not None
    assert tone.leakage_ratio >= _quality_config()["leakage"][
        "exclude_candidate_ratio"
    ]


def test_adjacent_legal_excited_tone_is_excluded_from_leakage_energy() -> None:
    spectrum_by_period = np.zeros((4, 201), dtype=np.complex128)
    spectrum_by_period[:, 100] = 10.0
    spectrum_by_period[:, 102] = 10.0
    estimate = PeriodTransferEstimate(
        frequency_hz=np.array([1000.0, 1020.0]),
        tone_bins=np.array([100, 102]),
        transfer_by_period=np.ones((4, 2), dtype=np.complex128),
        spectrum_by_period=spectrum_by_period,
        analysis_periods=np.zeros((4, 400)),
        normalized_correlation=np.ones(10),
        preamble_start_sample=0,
        first_period_start_sample=0,
        analysis_start_sample=0,
        period_samples=400,
        discarded_period_count=0,
        stable_period_count=4,
    )
    config = _quality_config()
    clipping = analyze_clipping(
        np.zeros(1600),
        config["clipping"],
        channel=0,
        sample_format="float64",
    )

    records, _, _ = evaluate_tone_and_audio_quality(
        estimate,
        np.zeros(2),
        config,
        clipping_metrics=clipping,
        clock_drift_metrics="unavailable",
    )

    assert records[0].leakage_ratio == pytest.approx(0.0)
    assert records[0].leakage_status == "valid"
    assert records[1].leakage_ratio == pytest.approx(0.0)
    assert records[1].leakage_status == "valid"


def test_period_gain_and_phase_jitter_is_reported_per_tone(tmp_path) -> None:
    meta, stimulus_manifest_path = _simulated_case(
        tmp_path,
        stable_period_gain_db=(0.0, 3.0, -3.0, 2.0, -2.0, 1.0, -1.0, 0.0),
        stable_period_shift_samples=(0, 2, -2, 1, -1, 3, -3, 0),
    )

    analysis = _analyze(meta, stimulus_manifest_path)

    assert any(
        record.period_variance_status == "exclude_candidate"
        for record in analysis.tone_quality
    )
    assert all(record.period_count == 8 for record in analysis.tone_quality)
    assert all(
        record.magnitude_variance_db2 is not None
        and record.phase_circular_variance is not None
        for record in analysis.tone_quality
    )


def test_period_stability_can_use_configured_power_variance(tmp_path) -> None:
    meta, stimulus_manifest_path = _simulated_case(tmp_path)
    quality = _quality_config()
    quality["period_stability"]["method"] = "power_relative_variance"

    analysis = _analyze(meta, stimulus_manifest_path, quality)

    assert all(
        record.period_variance_method == "power_relative_variance"
        for record in analysis.tone_quality
    )
    assert all(
        record.period_variance_status == "valid"
        for record in analysis.tone_quality
    )


@pytest.mark.parametrize("interference_hz", [50.0, 60.0, 600.0])
def test_non_excited_interference_and_harmonic_energy_is_detected(
    tmp_path,
    interference_hz: float,
) -> None:
    meta, stimulus_manifest_path = _simulated_case(
        tmp_path,
        interference_tones_dbfs={interference_hz: -35.0},
    )

    analysis = _analyze(meta, stimulus_manifest_path)
    off_tone = analysis.measurement_qc["non_excited_energy"]

    assert off_tone["status"] == "exclude_candidate"
    assert off_tone["energy_ratio"] >= _quality_config()["non_excited_energy"][
        "exclude_candidate_ratio"
    ]


def test_metrics_are_unavailable_when_their_evidence_is_insufficient(tmp_path) -> None:
    meta, stimulus_manifest_path = _simulated_case(tmp_path)
    quality = _quality_config()
    quality["neighborhood"]["minimum_noise_bins"] = 100
    quality["neighborhood"]["minimum_leakage_bins"] = 100
    quality["period_stability"]["minimum_periods"] = 20
    quality["non_excited_energy"]["minimum_bin_count"] = 10000

    analysis = _analyze(meta, stimulus_manifest_path, quality)

    assert all(record.snr_status == "unavailable" for record in analysis.tone_quality)
    assert all(
        record.leakage_status == "unavailable" for record in analysis.tone_quality
    )
    assert all(
        record.period_variance_status == "unavailable"
        for record in analysis.tone_quality
    )
    assert all(record.missing_tone is None for record in analysis.tone_quality)
    assert analysis.measurement_qc["status"] == "warning"
    assert analysis.measurement_qc["unavailable_items"] == [
        "leakage",
        "missing_tone",
        "non_excited_energy",
        "period_variance",
        "snr",
    ]


def test_multiple_qc_failures_preserve_all_reasons_and_manual_validity(tmp_path) -> None:
    meta, stimulus_manifest_path = _simulated_case(
        tmp_path,
        additive_noise_std=5.0e-3,
        interference_tones_dbfs={1020.0: -55.0, 50.0: -35.0},
        stable_period_gain_db=(0.0, 3.0, -3.0, 2.0, -2.0, 1.0, -1.0, 0.0),
        clipping_run_samples=32,
    )

    analysis = _analyze(meta, stimulus_manifest_path)
    tone = next(record for record in analysis.tone_quality if record.frequency_hz == 1000.0)

    assert len(tone.qc_reasons) >= 2
    assert analysis.measurement_qc["status"] == "exclude_candidate"
    assert analysis.spectrum.meta.valid is True
    assert analysis.spectrum.frequency_hz.size == 71


def test_warning_and_exclude_boundaries_are_inclusive_for_clipping() -> None:
    config = _quality_config()["clipping"]
    config["warning_fraction"] = 0.01
    config["exclude_candidate_fraction"] = 0.02
    audio = np.zeros(100, dtype=np.float64)
    audio[:1] = 1.0
    assert analyze_clipping(
        audio, config, channel=0, sample_format="float64"
    )["status"] == "warning"
    audio[:2] = 1.0
    assert analyze_clipping(
        audio, config, channel=0, sample_format="float64"
    )["status"] == "exclude_candidate"


def test_qc_output_bundle_contains_structured_tables_spectrum_and_plots(
    tmp_path,
) -> None:
    meta, stimulus_manifest_path = _simulated_case(tmp_path / "inputs")
    analysis = _analyze(meta, stimulus_manifest_path)

    artifacts = write_multisine_qc_outputs(
        analysis,
        tmp_path / "outputs",
        measurement_summary_filename="p8_measurement_qc.csv",
    )

    assert set(artifacts) == {
        "transfer_tones_csv",
        "tone_quality_csv",
        "clock_drift_qc_csv",
        "measurement_qc_csv",
        "spectrum_npz",
        "spectrum_json",
        "synchronization_diagnostic_png",
        "period_consistency_png",
    }
    assert all(path.is_file() and path.stat().st_size > 0 for path in artifacts.values())
    assert artifacts["measurement_qc_csv"].name == "p8_measurement_qc.csv"
    with artifacts["tone_quality_csv"].open(encoding="utf-8", newline="") as handle:
        tone_rows = list(csv.DictReader(handle))
    assert len(tone_rows) == 71
    assert {
        "frequency_hz",
        "snr_db",
        "snr_status",
        "leakage_ratio",
        "leakage_status",
        "period_variance",
        "period_variance_status",
        "missing_tone",
        "valid_tone",
        "qc_reasons",
    }.issubset(tone_rows[0])
    with artifacts["transfer_tones_csv"].open(
        encoding="utf-8", newline=""
    ) as handle:
        assert len(list(csv.DictReader(handle))) == 71
    roundtrip = load_spectrum(tmp_path / "outputs" / "spectrum_data")
    assert np.array_equal(roundtrip.frequency_hz, analysis.spectrum.frequency_hz)
    assert np.array_equal(roundtrip.valid_mask, analysis.spectrum.valid_mask)
    assert artifacts["synchronization_diagnostic_png"].read_bytes().startswith(
        b"\x89PNG\r\n\x1a\n"
    )
    assert artifacts["period_consistency_png"].read_bytes().startswith(
        b"\x89PNG\r\n\x1a\n"
    )
