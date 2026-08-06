from __future__ import annotations

import json

import pytest

from acoustic_encoder.cross_mode_bridge import _canonical_sha256, analyze_cross_mode_bridge
from acoustic_encoder.cross_mode_bridge_outputs import (
    load_cross_mode_bridge_bundle,
    write_cross_mode_bridge_outputs,
)
from acoustic_encoder.schemas import artifact_sha256

from test_cross_mode_bridge import _analysis_fixture, _fit_config


def _arguments(tmp_path):
    artifacts, scope, _, _ = _analysis_fixture()
    config = {
        "fit": _fit_config(),
        "evaluation": {"minimum_common_tones": 2, "minimum_pair_coverage": 1.0},
        "direction_templates": {"minimum_common_tones": 2},
        "classification": {"minimum_training_features": 2, "minimum_prediction_coverage": 1.0},
    }
    result = analyze_cross_mode_bridge(artifacts, scope, config)
    return result, scope, config, tmp_path / "bridge"


def test_bridge_outputs_are_complete_hashed_and_round_trip(tmp_path) -> None:
    result, scope, config, output = _arguments(tmp_path)
    paths = write_cross_mode_bridge_outputs(
        result,
        scope,
        config,
        {"schema_version": "1.0.0", "analysis_scope_id": scope.analysis_scope_id},
        output,
        input_file_hashes={"synthetic://fixture": "1" * 64},
        git_commit="f" * 40,
        git_dirty=True,
        created_at="2026-08-06T12:00:00+00:00",
    )

    required = {
        "bridge_scope.json", "input_manifest.json", "matched_pair_audit.csv",
        "fold_assignments.csv", "tone_authority_audit.csv",
        "uncalibrated_tone_comparison.csv", "calibration_parameters.csv",
        "calibration_fit_diagnostics.csv", "heldout_tone_comparison.csv",
        "direction_template_consistency.csv", "cross_mode_predictions.csv",
        "cross_mode_fold_metrics.csv", "cross_mode_summary.json",
        "calibration_model.json", "bridge_result.json", "bridge_manifest.json",
        "bridge_manifest.sha256", "calibration_model.sha256",
    }
    assert required <= {path.name for path in paths}
    bundle = load_cross_mode_bridge_bundle(output)
    assert bundle["result"]["result_semantic_sha256"] == result.sha256
    assert bundle["scope"].sha256 == scope.sha256
    assert len(bundle["models"]) == len(result.calibration_models)
    manifest = bundle["manifest"]
    assert manifest["scientifically_eligible"] is False
    assert manifest["deployment_eligible"] is False
    assert manifest["canonical_analysis"] is False
    assert manifest["final_test_read"] is False
    assert manifest["manifest_content_sha256"].startswith("sha256:")
    assert artifact_sha256(output / "bridge_manifest.json") == (
        output / "bridge_manifest.sha256"
    ).read_text(encoding="utf-8").split()[0]


def test_bridge_output_refuses_overwrite_and_detects_tampering(tmp_path) -> None:
    result, scope, config, output = _arguments(tmp_path)
    arguments = (
        result, scope, config,
        {"schema_version": "1.0.0", "analysis_scope_id": scope.analysis_scope_id},
        output,
    )
    keywords = {
        "input_file_hashes": {}, "git_commit": "f" * 40, "git_dirty": True,
    }
    write_cross_mode_bridge_outputs(*arguments, **keywords)
    with pytest.raises(FileExistsError):
        write_cross_mode_bridge_outputs(*arguments, **keywords)

    model_path = output / "calibration_model.json"
    payload = json.loads(model_path.read_text(encoding="utf-8"))
    payload["models"][0]["method"] = "tampered"
    model_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_cross_mode_bridge_bundle(output)


def test_bridge_bundle_recomputes_result_semantic_hash(tmp_path) -> None:
    result, scope, config, output = _arguments(tmp_path)
    write_cross_mode_bridge_outputs(
        result,
        scope,
        config,
        {"schema_version": "1.0.0", "analysis_scope_id": scope.analysis_scope_id},
        output,
        input_file_hashes={},
        git_commit="a" * 40,
        git_dirty=False,
    )
    result_path = output / "bridge_result.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload["processing_status"] = "tampered"
    result_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest_path = output / "bridge_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_hashes"]["bridge_result.json"] = artifact_sha256(result_path)
    semantic = dict(manifest)
    semantic.pop("manifest_content_sha256")
    manifest["manifest_content_sha256"] = _canonical_sha256(semantic)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "bridge_manifest.sha256").write_text(
        artifact_sha256(manifest_path) + "  bridge_manifest.json\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="result hash"):
        load_cross_mode_bridge_bundle(output)
