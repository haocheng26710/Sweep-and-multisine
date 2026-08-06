from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest
import yaml

from acoustic_encoder.cross_mode_bridge_cli import run_cross_mode_bridge_command
from acoustic_encoder.cross_mode_bridge_outputs import load_cross_mode_bridge_bundle
from acoustic_encoder.dataset_quality_control import feature_contract_sha256, feature_set_content_sha256
from acoustic_encoder.schemas import artifact_sha256, save_feature_set

from test_cross_mode_bridge import _analysis_fixture


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_inputs(tmp_path):
    artifacts, scope, _, _ = _analysis_fixture()
    input_root = tmp_path / "inputs"
    input_root.mkdir(parents=True)
    feature_rows = []
    for artifact_id, feature in sorted(artifacts.items()):
        base = input_root / "features" / artifact_id
        npz_path, json_path = save_feature_set(feature, base)
        lineage = []
        roles = ["p3c_preprocessing_manifest"]
        if artifact_id.startswith("multi"):
            roles += [
                "p7_stimulus_manifest", "p8_run_manifest", "p8_spectrum_npz",
                "p8_spectrum_json", "p8_tone_quality",
            ]
        for role in roles:
            path = input_root / "lineage" / artifact_id / f"{role}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"role": role, "sample_id": feature.sample_id}), encoding="utf-8")
            lineage.append({"role": role, "path": str(path), "file_sha256": artifact_sha256(path)})
        feature_rows.append({
            "artifact_id": artifact_id,
            "sample_id": feature.sample_id,
            "feature_base_path": str(base),
            "feature_npz_sha256": artifact_sha256(npz_path),
            "feature_json_sha256": artifact_sha256(json_path),
            "feature_content_sha256": feature_set_content_sha256(feature),
            "feature_contract_sha256": feature_contract_sha256(feature),
            "lineage": lineage,
        })
    authority_rows = []
    role_to_field = {
        "p2b_result": "p2b_result_sha256",
        "p4b_result": "p4b_result_sha256",
        "p9a_selection_scope": "p9a_selection_scope_sha256",
        "p9a_selection_artifact": "p9a_selection_artifact_sha256",
        "p9a_manifest": "p9a_manifest_sha256",
        "p9b_result": "p9b_result_sha256",
        "p9b_manifest": "p9b_manifest_sha256",
    }
    for fold in scope.outer_folds:
        for role, field in role_to_field.items():
            path = input_root / "authority" / fold.outer_fold_id / f"{role}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "authority_role": role,
                "outer_fold_id": fold.outer_fold_id,
                "authority_semantic_sha256": getattr(fold, field),
                "selection_scope_role": "fold_training_selection",
                "training_pair_ids": list(fold.training_pair_ids),
                "held_out_physical_state_ids": list(fold.held_out_physical_state_ids),
                "ordered_tone_ids": list(fold.ordered_tone_ids),
                "selected_subset_sha256": fold.selected_subset_sha256,
                "candidate_universe_sha256": fold.candidate_universe_sha256,
            }
            path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            authority_rows.append({
                "outer_fold_id": fold.outer_fold_id,
                "role": role,
                "path": str(path),
                "file_sha256": artifact_sha256(path),
                "authority_semantic_sha256": getattr(fold, field),
            })
    scope_path = input_root / "bridge_scope.json"
    scope_path.write_text(json.dumps(scope.to_dict(), sort_keys=True), encoding="utf-8")
    manifest = {
        "schema_version": "1.0.0",
        "analysis_scope_id": scope.analysis_scope_id,
        "analysis_scope_sha256": scope.sha256,
        "sealed_final_test_sample_ids": list(scope.sealed_final_test_sample_ids),
        "sealed_final_test_sha256": scope.sealed_final_test_sha256,
        "features": feature_rows,
        "fold_authorities": authority_rows,
    }
    manifest_path = input_root / "bridge_inputs.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    config = yaml.safe_load((PROJECT_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    config["cross_mode_bridge"]["enabled"] = True
    config["cross_mode_bridge"]["fit"]["minimum_pairs_per_tone"] = 3
    config["cross_mode_bridge"]["fit"]["minimum_input_variance_db2"] = 1.0e-8
    config["cross_mode_bridge"]["fit"]["residual_policy"] = {
        "warning_above_rms_db": 0.05, "unavailable_above_rms_db": 0.25,
    }
    config["cross_mode_bridge"]["classification"]["models"] = ["nearest_centroid"]
    config_path = input_root / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return scope, scope_path, manifest, manifest_path, config_path


def test_cli_loads_only_explicit_hashed_features_and_authorities(tmp_path) -> None:
    scope, scope_path, _, manifest_path, config_path = _write_inputs(tmp_path)
    status = run_cross_mode_bridge_command([
        "--config", str(config_path), "--scope", str(scope_path),
        "--inputs", str(manifest_path), "--output-root", str(tmp_path / "outputs"),
        "--run-id", "DEV-C14-cli", "--project-root", str(PROJECT_ROOT),
    ])

    output = tmp_path / "outputs" / "simulated" / "software_validation" / "DEV-C14-cli" / "cross_mode_bridge"
    bundle = load_cross_mode_bridge_bundle(output)
    assert status["processing_status"] in {
        "completed", "completed_with_warnings", "completed_with_unavailable"
    }
    assert status["scientifically_eligible"] is False
    assert status["deployment_eligible"] is False
    assert status["final_test_read"] is False
    assert bundle["scope"].sha256 == scope.sha256
    assert bundle["manifest"]["input_file_hashes"]


def test_cli_fails_closed_for_missing_lineage_or_authority_tampering(tmp_path) -> None:
    _, scope_path, manifest, manifest_path, config_path = _write_inputs(tmp_path)
    manifest["features"][0]["lineage"] = []
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    argv = [
        "--config", str(config_path), "--scope", str(scope_path),
        "--inputs", str(manifest_path), "--output-root", str(tmp_path / "outputs"),
        "--run-id", "bad-lineage", "--project-root", str(PROJECT_ROOT),
    ]
    with pytest.raises(ValueError, match="lineage"):
        run_cross_mode_bridge_command(argv)

    _, scope_path, manifest, manifest_path, config_path = _write_inputs(tmp_path / "second")
    authority_path = Path(manifest["fold_authorities"][0]["path"])
    authority_path.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        run_cross_mode_bridge_command([
            "--config", str(config_path), "--scope", str(scope_path),
            "--inputs", str(manifest_path), "--output-root", str(tmp_path / "outputs"),
            "--run-id", "bad-authority", "--project-root", str(PROJECT_ROOT),
        ])
