from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from acoustic_encoder.config import load_config
from acoustic_encoder.mock_data import generate_dual_mode_mock
from acoustic_encoder.p1_adapters import (
    P1AdapterError,
    P1ManualReviewRequired,
    load_multisine_measurement,
)
from acoustic_encoder.schemas import DataOrigin, Representation

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _adapter_case(tmp_path):
    stimulus_config = load_config(
        PROJECT_ROOT / "config" / "stimulus_multisine_broadband.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )["stimulus"]
    mock_root = tmp_path / "mock"
    mock_manifest_path = generate_dual_mode_mock(
        mock_root,
        deepcopy(stimulus_config),
        configurations=["U4ENC"],
        angles_deg=[0],
        random_state=123,
        recording_delay_samples=1379,
    )
    mock_manifest = json.loads(mock_manifest_path.read_text(encoding="utf-8"))
    sample = next(
        item
        for item in mock_manifest["samples"]
        if item["measurement_mode"] == "schroeder_multisine"
    )
    resolved = load_config(
        PROJECT_ROOT / "config" / "experiment_v2_u4_multisine.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    resolved["paths"]["stimuli"] = (mock_root / "stimuli").as_posix()
    return sample, resolved, stimulus_config


def test_p1_multisine_adapter_discovers_manifest_and_returns_sparse_spectrum(
    tmp_path,
) -> None:
    sample, resolved, stimulus_config = _adapter_case(tmp_path)

    spectrum = load_multisine_measurement(
        sample["source_path"],
        sample["sidecar_path"],
        None,
        resolved,
    )

    assert spectrum.representation is Representation.SPARSE_TONES
    assert spectrum.frequency_hz.size == 71
    assert spectrum.meta.data_origin is DataOrigin.SIMULATED
    assert spectrum.meta.eligible_for_scientific_analysis is False
    assert spectrum.meta.stimulus_id == stimulus_config["stimulus_id"]
    assert spectrum.quality_metrics["p8_qc"]["status"] == "valid"


def test_p1_multisine_adapter_rejects_config_tone_set_mismatch(tmp_path) -> None:
    sample, resolved, _ = _adapter_case(tmp_path)
    resolved["tone_set_id"] = "wrong-tone-set"

    with pytest.raises(P1AdapterError, match="configured tone_set_id mismatch"):
        load_multisine_measurement(
            sample["source_path"],
            sample["sidecar_path"],
            None,
            resolved,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("stimulus_hash", "0" * 64, "stimulus hash mismatch"),
        ("tone_set_id", "wrong-tone-set", "tone_set_id mismatch"),
        ("sample_rate_hz", 44100, "sample rate mismatch"),
        ("period_samples", 4096, "period_samples mismatch"),
        ("stable_period_count", 7, "stable period count mismatch"),
        ("discard_initial_period_count", 1, "discard period count mismatch"),
        ("audio_channel", 99, "channel 99 is unavailable"),
        ("source_format", "rew_txt", "Invalid multisine sidecar metadata"),
    ],
)
def test_p1_multisine_adapter_rejects_sidecar_inconsistency(
    tmp_path,
    field: str,
    value,
    message: str,
) -> None:
    sample, resolved, _ = _adapter_case(tmp_path)
    sidecar_path = Path(sample["sidecar_path"])
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar[field] = value
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(P1AdapterError, match=message):
        load_multisine_measurement(
            sample["source_path"],
            sidecar_path,
            None,
            resolved,
        )


def test_p1_multisine_adapter_requires_sidecar_stimulus_identity(tmp_path) -> None:
    sample, resolved, _ = _adapter_case(tmp_path)
    sidecar_path = Path(sample["sidecar_path"])
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    del sidecar["stimulus_id"]
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(P1AdapterError, match="sidecar fields.*stimulus_id"):
        load_multisine_measurement(
            sample["source_path"],
            sidecar_path,
            None,
            resolved,
        )


@pytest.mark.parametrize("audio_channel", [None, True, 0.5, -1])
def test_p1_multisine_adapter_requires_integer_nonnegative_audio_channel(
    tmp_path,
    audio_channel,
) -> None:
    sample, resolved, _ = _adapter_case(tmp_path)
    sidecar_path = Path(sample["sidecar_path"])
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["audio_channel"] = audio_channel
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(P1AdapterError, match="non-negative integer"):
        load_multisine_measurement(
            sample["source_path"],
            sidecar_path,
            None,
            resolved,
        )


def test_p1_multisine_adapter_stops_explicit_manual_review(tmp_path) -> None:
    sample, resolved, _ = _adapter_case(tmp_path)
    sidecar_path = Path(sample["sidecar_path"])
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["manual_review_reasons"] = ["unconfirmed_acquisition_mapping"]
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(P1ManualReviewRequired) as error:
        load_multisine_measurement(
            sample["source_path"],
            sidecar_path,
            None,
            resolved,
        )
    assert error.value.reasons == ("unconfirmed_acquisition_mapping",)


def test_p1_multisine_adapter_requires_canonical_manifest_path(tmp_path) -> None:
    sample, resolved, _ = _adapter_case(tmp_path)
    wrong_manifest = tmp_path / "unrelated" / "stimulus_manifest.json"
    wrong_manifest.parent.mkdir()
    wrong_manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(P1AdapterError, match="canonical stimulus_id path"):
        load_multisine_measurement(
            sample["source_path"],
            sample["sidecar_path"],
            wrong_manifest,
            resolved,
        )


def test_p1_multisine_adapter_rejects_stale_sidecar_manifest_pointer(tmp_path) -> None:
    sample, resolved, _ = _adapter_case(tmp_path)
    sidecar_path = Path(sample["sidecar_path"])
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["stimulus_manifest"] = (tmp_path / "stale" / "manifest.json").as_posix()
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(P1AdapterError, match="sidecar stimulus_manifest mismatch"):
        load_multisine_measurement(
            sample["source_path"],
            sidecar_path,
            None,
            resolved,
        )


def test_p1_multisine_adapter_wraps_malformed_canonical_manifest(tmp_path) -> None:
    sample, resolved, _ = _adapter_case(tmp_path)
    manifest = (
        Path(resolved["paths"]["stimuli"])
        / sample["stimulus_id"]
        / "stimulus_manifest.json"
    )
    manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(P1AdapterError, match="linkage fields"):
        load_multisine_measurement(
            sample["source_path"],
            sample["sidecar_path"],
            None,
            resolved,
        )
