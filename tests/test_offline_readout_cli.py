from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import numpy as np

from acoustic_encoder.config import load_config
from acoustic_encoder.dataset_quality_control import feature_set_content_sha256
from acoustic_encoder.offline_readout import canonical_sha256, normalize_sha256
from acoustic_encoder.offline_readout_cli import (
    build_readout_package_from_manifest,
    execute_offline_readout_from_manifest,
)
from acoustic_encoder.offline_readout_outputs import load_offline_readout_bundle, load_readout_package_bundle
from acoustic_encoder.quality_control import MeasurementQCResult, UnavailablePolicy
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import (
    DataOrigin, DatasetRole, MeasurementMeta, MeasurementMode, PhaseStatus,
    Representation, SourceFormat, SpectrumData, artifact_sha256, save_feature_set, save_spectrum,
)
from acoustic_encoder.stimulus_multisine import generate_multisine
from acoustic_encoder.tone_features import build_multisine_tone_feature_set
from acoustic_encoder.tone_sets import load_tone_set
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _file_sha(path: Path) -> str:
    return normalize_sha256(artifact_sha256(path))


def _qc(sample_id: str) -> MeasurementQCResult:
    return MeasurementQCResult(
        "1.0.0", sample_id, MeasurementMode.SCHROEDER_MULTISINE,
        DataOrigin.SIMULATED, DatasetRole.SOFTWARE_VALIDATION,
        RunPurpose.SOFTWARE_VALIDATION, (), UnavailablePolicy.WARNING, (), True, None, False,
    )


def _spectrum(sample_id: str, angle: float, values: np.ndarray, tone_set, waveform_hash: str) -> SpectrumData:
    meta = MeasurementMeta(
        sample_id=sample_id, **SCHEMA_VERSION_QUARTET, device_version="V2", configuration="U4ENC",
        angle_deg=angle, session_id="S01", repeat_type="CONT", repeat_id=sample_id,
        experiment_step="DEV_C15", measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        stimulus_id="dev-c15-readout-stimulus", stimulus_hash=waveform_hash,
        tone_set_id=tone_set.tone_set_id, sidecar_path=f"{sample_id}.json", audio_channel=0,
        source_format=SourceFormat.MOCK_AUDIO, source_path=f"{sample_id}.wav",
        data_origin=DataOrigin.SIMULATED, dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256=("1" if angle == 0 else "2" if angle == 90 else "3") * 64,
        provenance_uri="dev-c15-mock-manifest.json", eligible_for_scientific_analysis=False,
    )
    quality = [
        {"frequency_hz": float(frequency), "missing_tone": False, "valid_tone": True,
         "snr_db": 50.0, "snr_status": "valid", "qc_reasons": []}
        for frequency in tone_set.frequency_hz
    ]
    return SpectrumData(
        tone_set.frequency_hz, values, np.ones(values.size, dtype=bool), Representation.SPARSE_TONES,
        PhaseStatus.RELATIVE_UNRELIABLE,
        {"tone_set": {"tone_set_id": tone_set.tone_set_id, "tone_set_sha256": tone_set.tone_set_sha256,
                      "tones_sha256": tone_set.tones_sha256, "verified_artifacts": True},
         "tone_quality": quality, "synchronization_method": "preamble_cross_correlation",
         "clock_drift": {"final_decision": "valid", "correction_applied": False},
         "clipping": {"status": "valid", "clipped_sample_count": 0},
         "period_samples": tone_set.period_samples, "stable_period_count": 8,
         "p8_qc": {"aggregate_status": "valid"}},
        meta, None, "transfer_ratio", normalize_sha256(waveform_hash),
    )


def _prepare_cli_fixture(tmp_path: Path):
    resolved = load_config(PROJECT_ROOT / "config" / "validation_dev_c15_p9d.yaml",
                           default_path=PROJECT_ROOT / "config" / "default.yaml")
    stimulus = deepcopy(load_config(PROJECT_ROOT / "config" / "stimulus_multisine_broadband.yaml",
                                    default_path=PROJECT_ROOT / "config" / "default.yaml")["stimulus"])
    stimulus.update(stimulus_id="dev-c15-readout-stimulus", tone_set_id="dev-c15-readout-tones")
    stimulus["tones"] = {"mode": "explicit", "source": "software_validation_candidate",
                         "frequencies_hz": [1000, 1100, 1200]}
    p7 = generate_multisine(stimulus, tmp_path / "stimulus")
    stimulus_manifest = json.loads(p7.manifest_path.read_text(encoding="utf-8"))
    tone_set = load_tone_set(p7.manifest_path)
    values_by_direction = {
        0.0: (np.asarray([-3.0, 1.0, 2.0]), np.asarray([-2.8, 1.2, 1.6])),
        90.0: (np.asarray([-2.0, 4.0, -1.0]), np.asarray([-1.8, 3.8, -1.1])),
        180.0: (np.asarray([2.0, -1.0, -1.0]), np.asarray([1.8, -0.8, -1.0])),
    }
    entries = []
    for angle, rows in values_by_direction.items():
        for repeat, row in enumerate(rows):
            sample_id = f"train-{int(angle):03d}-{repeat}"
            feature = build_multisine_tone_feature_set(
                _spectrum(sample_id, angle, row, tone_set, stimulus_manifest["waveform_sha256"]),
                _qc(sample_id), tone_set, resolved["matched_tone_features"],
            ).feature_set
            assert feature is not None
            base = tmp_path / "training" / sample_id
            npz_path, json_path = save_feature_set(feature, base)
            entries.append({
                "sample_id": sample_id, "cohort_role": "development",
                "feature_base_path": base.as_posix(), "feature_json_sha256": _file_sha(json_path),
                "feature_npz_sha256": _file_sha(npz_path),
                "feature_content_sha256": feature_set_content_sha256(feature),
            })
    authorities = {}
    ordered_training_ids = [entry["sample_id"] for entry in entries]
    for name in ("p2b", "p4b", "p5", "p9a", "p9b"):
        path = tmp_path / "authorities" / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "authority": name, "lifecycle": "software_validation_candidate",
            "explicit_training_sample_ids": ordered_training_ids,
            "selected_tone_frequencies_hz": list(tone_set.frequency_hz) if name in {"p9a", "p9b"} else None,
            "final_test_read": False, "scientifically_eligible": False, "deployment_eligible": False,
        }), encoding="utf-8")
        authorities[name] = {"path": path.as_posix(), "sha256": _file_sha(path)}
    final_ids = ("sealed-final-001",)
    training_manifest = {
        "schema_version": "1.0.0", "package_id": "DEV-C15-cli-package",
        "created_utc": "2026-08-06T12:00:00Z", "direction_order_deg": [0.0, 90.0, 180.0],
        "stimulus_manifest_path": p7.manifest_path.as_posix(),
        "stimulus_manifest_file_sha256": _file_sha(p7.manifest_path),
        "training_features": entries, "authority_files": authorities,
        "sealed_final_test_sample_ids": list(final_ids),
        "sealed_final_test_sha256": canonical_sha256({"ordered_sample_ids": list(final_ids)}),
    }
    training_manifest_path = tmp_path / "training_manifest.json"
    training_manifest_path.write_text(json.dumps(training_manifest), encoding="utf-8")
    return resolved, p7, stimulus_manifest, tone_set, training_manifest_path


def test_two_cli_entry_points_build_then_infer_without_training_in_readout(tmp_path, monkeypatch) -> None:
    resolved, p7, stimulus_manifest, tone_set, training_manifest = _prepare_cli_fixture(tmp_path)
    package_dir = tmp_path / "package"
    build_readout_package_from_manifest(
        PROJECT_ROOT / "config" / "validation_dev_c15_p9d.yaml", training_manifest,
        package_dir, default_config_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    package, model, _ = load_readout_package_bundle(package_dir)
    assert len(model.training_sample_ids) == 6
    assert package.final_test_read is False

    spectrum = _spectrum("readout-090", 90.0, np.asarray([-2.0, 4.0, -1.0]),
                         tone_set, stimulus_manifest["waveform_sha256"])
    input_root = tmp_path / "input"
    spectrum_npz, spectrum_json = save_spectrum(spectrum, input_root / "spectrum_data")
    qc_path = input_root / "measurement_qc.json"
    qc_path.write_text(json.dumps(_qc(spectrum.meta.sample_id).to_dict()), encoding="utf-8")
    p8_manifest = input_root / "p8_manifest.json"
    p8_manifest.write_text(json.dumps({"sample_id": spectrum.meta.sample_id}), encoding="utf-8")
    tone_quality = input_root / "tone_quality.csv"
    tone_quality.write_text("frequency_hz,status\n1000,valid\n", encoding="utf-8")
    metadata = input_root / "metadata.json"
    metadata.write_text(json.dumps(spectrum.meta.to_dict()), encoding="utf-8")
    input_manifest = {
        "schema_version": "1.0.0", "spectrum_base_path": (input_root / "spectrum_data").as_posix(),
        "spectrum_json_sha256": _file_sha(spectrum_json), "spectrum_npz_sha256": _file_sha(spectrum_npz),
        "p8_manifest_path": p8_manifest.as_posix(), "p8_manifest_sha256": _file_sha(p8_manifest),
        "tone_quality_path": tone_quality.as_posix(), "tone_quality_sha256": _file_sha(tone_quality),
        "measurement_qc_path": qc_path.as_posix(), "measurement_qc_sha256": _file_sha(qc_path),
        "metadata_path": metadata.as_posix(), "metadata_sha256": _file_sha(metadata),
        "stimulus_manifest_path": p7.manifest_path.as_posix(),
    }
    input_manifest_path = tmp_path / "readout_input.json"
    input_manifest_path.write_text(json.dumps(input_manifest), encoding="utf-8")

    import acoustic_encoder.direction_models as direction_models
    monkeypatch.setattr(direction_models, "fit_frozen_direction_model", lambda *a, **k: (_ for _ in ()).throw(AssertionError("fit called during inference")))
    output = tmp_path / "readout"
    execute_offline_readout_from_manifest(package_dir, input_manifest_path, output)
    result, _ = load_offline_readout_bundle(output)

    assert result.prediction.available is True
    assert result.prediction.predicted_direction_deg == 90.0
    assert result.prediction.second_direction_deg is not None
    assert result.prediction.margin is not None
    assert result.processing_status == "completed_with_warnings"
    assert result.final_test_read is False
    assert result.scientifically_eligible is False
    assert result.deployment_eligible is False
