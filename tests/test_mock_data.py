from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from acoustic_encoder.config import load_config
from acoustic_encoder.mock_data import generate_dual_mode_mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _test_stimulus() -> dict:
    resolved = load_config(
        PROJECT_ROOT / "config" / "stimulus_multisine_broadband.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    stimulus = deepcopy(resolved["stimulus"])
    stimulus["tones"] = {
        "mode": "explicit",
        "source": "test_fixture",
        "frequencies_hz": [1000, 2000, 3000, 4000],
    }
    stimulus["discard_initial_period_count"] = 1
    stimulus["stable_period_count"] = 2
    return stimulus


def test_dual_mode_mock_uses_matching_conditions(tmp_path) -> None:
    stimulus = _test_stimulus()
    manifest_path = generate_dual_mode_mock(
        tmp_path,
        stimulus,
        configurations=["U4ENC"],
        angles_deg=[0, 90],
        random_state=123,
        recording_delay_samples=1379,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["mock_only"] is True
    assert manifest["mock_schema_version"] == "1.2.0"
    assert manifest["recording_delay_samples"] == 1379
    assert manifest["recording_wav_format"] == "float32"
    assert manifest["additive_noise_std"] == 2.0e-5
    assert len(manifest["samples"]) == 4
    for sample in manifest["samples"]:
        assert sample["data_origin"] == "simulated"
        assert sample["dataset_role"] == "software_validation"
        assert sample["eligible_for_scientific_analysis"] is False
        assert len(sample["source_sha256"]) == 64
        assert sample["source_sha256"] == hashlib.sha256(
            Path(sample["source_path"]).read_bytes()
        ).hexdigest()
        assert sample["provenance_uri"].endswith("mock_manifest.json")
    assert len(list((tmp_path / "rew").glob("*.txt"))) == 2
    audio_paths = sorted((tmp_path / "multisine").glob("*.wav"))
    assert len(audio_paths) == 2
    _, first = wavfile.read(audio_paths[0])
    _, second = wavfile.read(audio_paths[1])
    assert not np.array_equal(first, second)
    for sidecar_path in (tmp_path / "multisine").glob("*.json"):
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        assert sidecar["mock_only"] is True
        assert sidecar["recording_delay_samples"] == 1379
        assert sidecar["period_samples"] == stimulus["period_samples"]
        assert sidecar["common_sampling_clock"] is False
        assert sidecar["stimulus_hash"]
        assert sidecar["tone_set_id"] == stimulus["tone_set_id"]


def test_s3_positive_clock_drift_stretches_time_axis_and_is_auditable(tmp_path) -> None:
    stimulus = _test_stimulus()
    common = {
        "stimulus_config": stimulus,
        "configurations": ["U4ENC"],
        "angles_deg": [0],
        "random_state": 123,
        "recording_delay_samples": 1379,
    }
    zero_manifest_path = generate_dual_mode_mock(tmp_path / "zero", **common)
    positive_manifest_path = generate_dual_mode_mock(
        tmp_path / "positive",
        sampling_clock_drift_ppm=100.0,
        **common,
    )
    zero_manifest = json.loads(zero_manifest_path.read_text(encoding="utf-8"))
    positive_manifest = json.loads(positive_manifest_path.read_text(encoding="utf-8"))
    zero_audio_path = next((tmp_path / "zero" / "multisine").glob("*.wav"))
    positive_audio_path = next((tmp_path / "positive" / "multisine").glob("*.wav"))
    _, zero_audio = wavfile.read(zero_audio_path)
    _, positive_audio = wavfile.read(positive_audio_path)
    sidecar = json.loads(positive_audio_path.with_suffix(".json").read_text(encoding="utf-8"))

    assert positive_audio.size > zero_audio.size
    assert positive_manifest["sampling_clock_drift_ppm"] == 100.0
    assert positive_manifest["recording_delay_samples"] == 1379
    assert zero_manifest["sampling_clock_drift_ppm"] == 0.0
    assert sidecar["sampling_clock_drift_ppm"] == 100.0
    assert sidecar["clock_drift_simulation_method"] == "cubic_spline_time_axis_resampling"
    assert sidecar["common_sampling_clock"] is False


def test_s3_negative_clock_drift_compresses_time_axis(tmp_path) -> None:
    stimulus = _test_stimulus()
    common = {
        "stimulus_config": stimulus,
        "configurations": ["U4ENC"],
        "angles_deg": [0],
        "random_state": 123,
        "recording_delay_samples": 1379,
    }
    generate_dual_mode_mock(tmp_path / "zero", **common)
    generate_dual_mode_mock(
        tmp_path / "negative",
        sampling_clock_drift_ppm=-100.0,
        **common,
    )
    zero_audio_path = next((tmp_path / "zero" / "multisine").glob("*.wav"))
    negative_audio_path = next((tmp_path / "negative" / "multisine").glob("*.wav"))
    _, zero_audio = wavfile.read(zero_audio_path)
    _, negative_audio = wavfile.read(negative_audio_path)
    sidecar = json.loads(negative_audio_path.with_suffix(".json").read_text(encoding="utf-8"))

    assert negative_audio.size < zero_audio.size
    assert sidecar["sampling_clock_drift_ppm"] == -100.0
    assert sidecar["recording_delay_samples"] == 1379
