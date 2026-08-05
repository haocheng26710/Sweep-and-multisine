from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from acoustic_encoder.config import load_config
from acoustic_encoder.schemas import artifact_sha256
from acoustic_encoder.stimulus_multisine import generate_multisine
from acoustic_encoder.tone_sets import ToneSetValidationError, load_tone_set


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _stimulus_config() -> dict:
    resolved = load_config(
        PROJECT_ROOT / "config" / "stimulus_multisine_broadband.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    return resolved["stimulus"]


def test_generated_p7_artifacts_load_as_verified_tone_set(tmp_path: Path) -> None:
    artifacts = generate_multisine(_stimulus_config(), tmp_path)
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))

    tone_set = load_tone_set(artifacts.manifest_path)

    assert manifest["manifest_schema_version"] == "1.1.0"
    assert manifest["tones_sha256"] == artifact_sha256(artifacts.tones_path)
    assert manifest["tone_set_sha256"] == tone_set.tone_set_sha256
    assert tone_set.verified_artifacts is True
    assert tone_set.tone_set_id == manifest["tone_set_id"]
    assert tuple(tone.tone_index for tone in tone_set.tones) == tuple(
        range(manifest["tone_count"])
    )
    assert all(
        left.frequency_hz < right.frequency_hz
        for left, right in zip(tone_set.tones, tone_set.tones[1:])
    )


def test_tone_set_rejects_tampered_tones_file(tmp_path: Path) -> None:
    artifacts = generate_multisine(_stimulus_config(), tmp_path)
    artifacts.tones_path.write_text(
        artifacts.tones_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ToneSetValidationError, match="tones.csv SHA-256 mismatch"):
        load_tone_set(artifacts.manifest_path)


def test_tone_set_rejects_non_authoritative_csv_order(tmp_path: Path) -> None:
    artifacts = generate_multisine(_stimulus_config(), tmp_path)
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    with artifacts.tones_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0], rows[1] = rows[1], rows[0]
    with artifacts.tones_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest["tones_sha256"] = artifact_sha256(artifacts.tones_path)
    artifacts.manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ToneSetValidationError, match="tone_index order"):
        load_tone_set(artifacts.manifest_path)


def test_tone_set_rejects_duplicate_frequency(tmp_path: Path) -> None:
    artifacts = generate_multisine(_stimulus_config(), tmp_path)
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    with artifacts.tones_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[1]["frequency_hz"] = rows[0]["frequency_hz"]
    with artifacts.tones_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest["tones_sha256"] = artifact_sha256(artifacts.tones_path)
    artifacts.manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ToneSetValidationError, match="strictly increasing"):
        load_tone_set(artifacts.manifest_path)


def test_tone_set_rejects_manifest_and_resolved_tone_set_id_mismatch(
    tmp_path: Path,
) -> None:
    artifacts = generate_multisine(_stimulus_config(), tmp_path)
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    manifest["tone_set_id"] = "different-tone-set"
    artifacts.manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ToneSetValidationError, match="resolved stimulus config"):
        load_tone_set(artifacts.manifest_path)
