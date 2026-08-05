from __future__ import annotations

import json
from pathlib import Path

from acoustic_encoder.comparison_metrics_cli import run_comparison_metrics_cli
from acoustic_encoder.schemas import artifact_sha256, save_feature_set

from test_comparison_metrics_outputs import PROJECT_ROOT, _fixture


def _write_inputs(tmp_path: Path):
    artifacts, scope, _, _ = _fixture()
    feature_dir = tmp_path / "features"
    feature_dir.mkdir()
    entries = []
    for artifact_id, feature in artifacts.items():
        base = feature_dir / artifact_id
        save_feature_set(feature, base)
        entries.append(
            {
                "artifact_id": artifact_id,
                "sample_id": feature.sample_id,
                "feature_base_path": base.as_posix(),
                "feature_npz_sha256": artifact_sha256(base.with_suffix(".npz")),
                "feature_json_sha256": artifact_sha256(base.with_suffix(".json")),
            }
        )
    scope_path = tmp_path / "comparison_scope.json"
    scope_path.write_text(
        json.dumps(scope.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    inputs_path = tmp_path / "comparison_inputs.json"
    inputs_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "analysis_scope_id": scope.analysis_scope.analysis_scope_id,
                "data_origin": "simulated",
                "run_purpose": "software_validation",
                "features": entries,
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    return scope_path, inputs_path


def test_explicit_comparison_cli_runs_end_to_end_without_directory_discovery(
    tmp_path, capsys
) -> None:
    scope_path, inputs_path = _write_inputs(tmp_path)
    output_root = tmp_path / "outputs"
    status = run_comparison_metrics_cli(
        [
            "--config", str(PROJECT_ROOT / "config" / "default.yaml"),
            "--scope", str(scope_path),
            "--inputs", str(inputs_path),
            "--output-root", str(output_root),
            "--run-id", "DEV-C7-cli",
        ],
        project_root=PROJECT_ROOT,
    )

    assert status == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["canonical_analysis"] is False
    assert summary["scientifically_eligible"] is False
    output = output_root / "simulated" / "software_validation" / "DEV-C7-cli" / "comparison_metrics"
    assert (output / "metrics_manifest.json").is_file()
    assert (output / "band_metrics.csv").is_file()


def test_cli_hash_mismatch_writes_failed_manifest(tmp_path) -> None:
    scope_path, inputs_path = _write_inputs(tmp_path)
    payload = json.loads(inputs_path.read_text(encoding="utf-8"))
    payload["features"][0]["feature_npz_sha256"] = "sha256:" + "0" * 64
    inputs_path.write_text(json.dumps(payload), encoding="utf-8")
    output_root = tmp_path / "outputs"

    status = run_comparison_metrics_cli(
        [
            "--config", str(PROJECT_ROOT / "config" / "default.yaml"),
            "--scope", str(scope_path),
            "--inputs", str(inputs_path),
            "--output-root", str(output_root),
            "--run-id", "DEV-C7-failure",
        ],
        project_root=PROJECT_ROOT,
    )

    assert status == 1
    manifest_path = output_root / "simulated" / "software_validation" / "DEV-C7-failure" / "comparison_metrics" / "metrics_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["processing_status"] == "failed"
    assert manifest["success"] is False
    assert "hash mismatch" in manifest["failure"]["message"]
