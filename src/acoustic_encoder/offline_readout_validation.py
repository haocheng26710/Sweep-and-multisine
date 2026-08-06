"""Deterministic persisted P7 -> S3 -> P8 -> P9-D software validation."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
from typing import Any

from .config import load_config
from .dataset_quality_control import feature_set_content_sha256
from .matched_tone_validation import run_simulated_matched_tone_validation
from .offline_readout import canonical_sha256, normalize_sha256
from .offline_readout_cli import build_readout_package_from_manifest, execute_offline_readout_from_manifest
from .offline_readout_outputs import load_offline_readout_bundle, load_readout_package_bundle
from .quality_control import evaluate_measurement_quality
from .schemas import artifact_sha256, load_spectrum


def _file_sha(path: Path) -> str:
    return normalize_sha256(artifact_sha256(path))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git_state(project: Path) -> tuple[str, bool]:
    commit = subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=project, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ("git", "status", "--porcelain"), cwd=project, check=True,
        capture_output=True, text=True,
    ).stdout.strip())
    return commit, dirty


def run_offline_readout_validation(
    *, project_root: str | Path, config_path: str | Path,
    output_root: str | Path, run_id: str,
) -> dict[str, Any]:
    project = Path(project_root).resolve()
    run_root = Path(output_root).resolve() / "simulated" / "software_validation" / run_id
    if run_root.exists():
        raise FileExistsError(f"offline readout validation run already exists: {run_root}")
    run_root.mkdir(parents=True, exist_ok=False)
    resolved = load_config(config_path, default_path=project / "config" / "default.yaml")
    source_commit, source_git_dirty = _git_state(project)
    sweep_config = load_config(project / "config" / "experiment_v2_u4.yaml", default_path=project / "config" / "default.yaml")
    multisine_config = load_config(project / "config" / "experiment_v2_u4_multisine.yaml", default_path=project / "config" / "default.yaml")
    stimulus = load_config(project / "config" / "stimulus_multisine_broadband.yaml", default_path=project / "config" / "default.yaml")["stimulus"]
    selected_frequencies = [1000, 2000, 4000, 5000, 6000]
    stimulus.update(
        stimulus_id="c15s",
        tone_set_id="c15t",
    )
    stimulus["tones"] = {
        "mode": "explicit", "source": "p9a_p9b_software_validation_candidate",
        "frequencies_hz": selected_frequencies,
    }
    multisine_config["stimulus_id"] = stimulus["stimulus_id"]
    multisine_config["tone_set_id"] = stimulus["tone_set_id"]
    for config in (sweep_config, multisine_config):
        config["matched_tone_features"] = deepcopy(resolved["matched_tone_features"])
    chains = []
    for session_index, session in enumerate(("S01", "S02")):
        for direction in (0, 90, 180):
            chains.append(run_simulated_matched_tone_validation(
                output_root=run_root / "c", run_id=f"t{session_index}{direction // 90}",
                sweep_config=deepcopy(sweep_config), multisine_config=deepcopy(multisine_config),
                stimulus_config=deepcopy(stimulus), random_state=20260806 + session_index * 100 + direction,
                recording_delay_samples=1379 + session_index * 17, session_id=session, angle_deg=direction,
            ))
    readout_chain = run_simulated_matched_tone_validation(
        output_root=run_root / "c", run_id="r90",
        sweep_config=deepcopy(sweep_config), multisine_config=deepcopy(multisine_config),
        stimulus_config=deepcopy(stimulus), random_state=20261196,
        recording_delay_samples=1493, session_id="S03", angle_deg=90,
    )
    authority_root = run_root / "authorities"
    training_ids = tuple(chain.multisine_result.feature_set.sample_id for chain in chains if chain.multisine_result.feature_set is not None)
    authority_entries: dict[str, dict[str, str]] = {}
    for stage in ("p2b", "p4b", "p5", "p9a", "p9b"):
        authority_path = authority_root / f"{stage}_authority.json"
        _write_json(authority_path, {
            "schema_version": "1.0.0", "stage": stage,
            "lifecycle": "software_validation_candidate",
            "explicit_training_sample_ids": list(training_ids),
            "selected_tone_frequencies_hz": selected_frequencies if stage in {"p9a", "p9b"} else None,
            "final_test_read": False, "scientifically_eligible": False,
            "deployment_eligible": False, "source_commit": source_commit,
            "source_git_dirty": source_git_dirty,
        })
        authority_entries[stage] = {"path": authority_path.as_posix(), "sha256": _file_sha(authority_path)}
    training_entries = []
    for chain in chains:
        feature = chain.multisine_result.feature_set
        if feature is None:
            raise RuntimeError("DEV-C15 training chain did not produce a multisine FeatureSet")
        base = chain.output_directory / "processed" / "features" / feature.feature_kind.value / feature.sample_id
        training_entries.append({
            "sample_id": feature.sample_id, "cohort_role": "development",
            "feature_base_path": base.as_posix(),
            "feature_npz_sha256": _file_sha(base.with_suffix(".npz")),
            "feature_json_sha256": _file_sha(base.with_suffix(".json")),
            "feature_content_sha256": feature_set_content_sha256(feature),
        })
    final_ids = ("sealed-final-validation-placeholder",)
    training_manifest = {
        "schema_version": "1.0.0", "package_id": "DEV-C15-P9D-SIMULATED-V1",
        "created_utc": "2026-08-06T12:00:00Z", "direction_order_deg": [0.0, 90.0, 180.0],
        "stimulus_manifest_path": chains[0].stimulus_manifest_path.as_posix(),
        "stimulus_manifest_file_sha256": _file_sha(chains[0].stimulus_manifest_path),
        "training_features": training_entries, "authority_files": authority_entries,
        "sealed_final_test_sample_ids": list(final_ids),
        "sealed_final_test_sha256": canonical_sha256({"ordered_sample_ids": list(final_ids)}),
    }
    training_manifest_path = run_root / "package_training_manifest.json"
    _write_json(training_manifest_path, training_manifest)
    package_dir = run_root / "readout_package"
    build_readout_package_from_manifest(
        config_path, training_manifest_path, package_dir,
        default_config_path=project / "config" / "default.yaml",
    )
    package, model, package_manifest = load_readout_package_bundle(package_dir)

    p8_dir = readout_chain.output_directory / "p8"
    spectrum_base = p8_dir / "spectrum_data"
    spectrum = load_spectrum(spectrum_base)
    measurement_qc = evaluate_measurement_quality(
        spectrum, multisine_config["quality_control"], run_purpose="software_validation"
    )
    qc_path = run_root / "readout_input" / "measurement_qc.json"
    metadata_path = run_root / "readout_input" / "measurement_metadata.json"
    _write_json(qc_path, measurement_qc.to_dict())
    _write_json(metadata_path, spectrum.meta.to_dict())
    input_manifest = {
        "schema_version": "1.0.0", "spectrum_base_path": spectrum_base.as_posix(),
        "spectrum_json_sha256": _file_sha(spectrum_base.with_suffix(".json")),
        "spectrum_npz_sha256": _file_sha(spectrum_base.with_suffix(".npz")),
        "p8_manifest_path": (p8_dir / "run_manifest.json").as_posix(),
        "p8_manifest_sha256": _file_sha(p8_dir / "run_manifest.json"),
        "tone_quality_path": (p8_dir / "tone_quality.csv").as_posix(),
        "tone_quality_sha256": _file_sha(p8_dir / "tone_quality.csv"),
        "measurement_qc_path": qc_path.as_posix(), "measurement_qc_sha256": _file_sha(qc_path),
        "metadata_path": metadata_path.as_posix(), "metadata_sha256": _file_sha(metadata_path),
        "stimulus_manifest_path": readout_chain.stimulus_manifest_path.as_posix(),
    }
    input_manifest_path = run_root / "readout_input_manifest.json"
    _write_json(input_manifest_path, input_manifest)
    first_output = run_root / "offline_readout"
    second_output = run_root / "offline_readout_repeat"
    execute_offline_readout_from_manifest(package_dir, input_manifest_path, first_output)
    execute_offline_readout_from_manifest(package_dir, input_manifest_path, second_output)
    result, readout_manifest = load_offline_readout_bundle(first_output)
    repeated, _ = load_offline_readout_bundle(second_output)
    if result.semantic_sha256 != repeated.semantic_sha256:
        raise RuntimeError("repeated offline readout was not deterministic")
    if result.prediction.predicted_direction_deg != 90.0:
        raise RuntimeError("known simulated direction was not recovered")
    summary = {
        "schema_version": "1.0.0", "processing_status": result.processing_status,
        "true_direction_deg": 90.0,
        "predicted_direction_deg": result.prediction.predicted_direction_deg,
        "second_direction_deg": result.prediction.second_direction_deg,
        "score": result.prediction.score, "second_score": result.prediction.second_score,
        "margin": result.prediction.margin, "qc_status": result.qc_audit.status,
        "calibration_applied": result.calibration_audit.applied,
        "training_sample_count": len(model.training_sample_ids),
        "tone_count": len(package.ordered_tone_ids), "model_id": model.model_id,
        "model_semantic_sha256": model.semantic_sha256,
        "package_semantic_sha256": package.semantic_sha256,
        "package_manifest_content_sha256": package_manifest["manifest_content_sha256"],
        "readout_result_sha256": result.semantic_sha256,
        "readout_manifest_content_sha256": readout_manifest["manifest_content_sha256"],
        "stimulus_id": package.stimulus_id,
        "stimulus_manifest_file_sha256": package.stimulus_manifest_file_sha256,
        "tone_set_id": package.tone_set_id, "tone_set_sha256": package.tone_set_sha256,
        "preprocessing_snapshot_sha256": package.p3_preprocessing_snapshot_sha256,
        "final_test_read": result.final_test_read,
        "scientifically_eligible": result.scientifically_eligible,
        "deployment_eligible": result.deployment_eligible,
        "deterministic_repeat": result.semantic_sha256 == repeated.semantic_sha256,
        "source_commit": source_commit, "source_git_dirty": source_git_dirty,
        "output_directory": run_root.as_posix(),
    }
    _write_json(run_root / "validation_summary.json", summary)
    return summary
