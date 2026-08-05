from __future__ import annotations

import csv
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from acoustic_encoder.config import load_config
from acoustic_encoder.stimulus_multisine import generate_multisine

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def stimulus_config() -> dict:
    resolved = load_config(
        PROJECT_ROOT / "config" / "stimulus_multisine_broadband.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    return resolved["stimulus"]


def test_p7_outputs_integer_bin_periodic_stimulus(tmp_path) -> None:
    config = stimulus_config()
    artifacts = generate_multisine(config, tmp_path)
    sample_rate, waveform = wavfile.read(artifacts.wav_path)
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    with artifacts.tones_path.open(encoding="utf-8", newline="") as handle:
        tones = list(csv.DictReader(handle))

    assert sample_rate == config["sample_rate_hz"]
    assert waveform.size == manifest["total_samples"]
    assert manifest["phase_formula"] == "phi_m = -pi*m*(m-1)/M, m=0..M-1"
    bins = np.array([int(row["dft_bin"]) for row in tones])
    frequencies = np.array([float(row["frequency_hz"]) for row in tones])
    np.testing.assert_allclose(
        frequencies,
        bins * sample_rate / config["period_samples"],
        atol=1e-12,
    )
    start = manifest["analysis_start_sample"]
    period = waveform[start : start + config["period_samples"]].astype(np.float64)
    tone_fft = np.abs(np.fft.rfft(period))[bins]
    assert np.all(tone_fft > 0)
    expected_peak = 10 ** (config["target_peak_dbfs"] / 20)
    assert np.max(np.abs(waveform)) <= expected_peak + 1e-6
    calculated_crest = np.max(np.abs(period)) / np.sqrt(np.mean(period**2))
    assert np.isclose(calculated_crest, manifest["crest_factor_linear"], rtol=1e-6)


def test_p7_same_config_produces_same_wav_hash(tmp_path) -> None:
    config = stimulus_config()
    first = generate_multisine(config, tmp_path / "first")
    second = generate_multisine(config, tmp_path / "second")
    assert first.waveform_sha256 == second.waveform_sha256


def test_analysis_period_has_no_fade(tmp_path) -> None:
    config = stimulus_config()
    artifacts = generate_multisine(config, tmp_path)
    _, waveform = wavfile.read(artifacts.wav_path)
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    start = manifest["analysis_start_sample"]
    period_samples = manifest["period_samples"]
    first = waveform[start : start + period_samples]
    second = waveform[start + period_samples : start + 2 * period_samples]
    np.testing.assert_array_equal(first, second)


def test_p7_rejects_non_increasing_explicit_tone_order(tmp_path) -> None:
    config = deepcopy(stimulus_config())
    config["tones"] = {
        "mode": "explicit",
        "source": "synthetic_invalid_order",
        "frequencies_hz": [1100, 1000],
    }

    with pytest.raises(ValueError, match="strictly increasing"):
        generate_multisine(config, tmp_path)
