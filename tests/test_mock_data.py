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


def test_dual_mode_mock_uses_matching_conditions(tmp_path) -> None:
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
    manifest_path = generate_dual_mode_mock(
        tmp_path,
        stimulus,
        configurations=["U4ENC"],
        angles_deg=[0, 90],
        random_state=123,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["mock_only"] is True
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
        assert sidecar["stimulus_hash"]
        assert sidecar["tone_set_id"] == stimulus["tone_set_id"]
