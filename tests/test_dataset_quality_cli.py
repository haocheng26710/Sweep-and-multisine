from __future__ import annotations

import json
from pathlib import Path

import yaml

from acoustic_encoder.dataset_quality_cli import run_dataset_quality_cli
from acoustic_encoder.schemas import artifact_sha256, save_feature_set
from test_dataset_quality_control import _measurement, _scope


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_explicit_dataset_scope_cli_runs_without_directory_discovery(
    tmp_path: Path,
) -> None:
    pairs = (
        _measurement("cli-cont-01", repeat_id="R01"),
        _measurement("cli-cont-02", repeat_id="R02"),
    )
    scope = _scope(("cli-cont-01", "cli-cont-02"))
    scope_path = tmp_path / "scope.yaml"
    scope_path.write_text(
        yaml.safe_dump(scope.to_dict(), sort_keys=False),
        encoding="utf-8",
    )
    measurements = []
    for feature, measurement_qc in pairs:
        feature_base = tmp_path / "features" / feature.sample_id
        feature_npz, feature_json = save_feature_set(feature, feature_base)
        qc_path = tmp_path / "p2a" / feature.sample_id / "quality_control.json"
        qc_path.parent.mkdir(parents=True, exist_ok=True)
        qc_path.write_text(
            json.dumps(measurement_qc.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        measurements.append(
            {
                "sample_id": feature.sample_id,
                "feature_base_path": feature_base.as_posix(),
                "feature_npz_sha256": artifact_sha256(feature_npz),
                "feature_json_sha256": artifact_sha256(feature_json),
                "measurement_qc_path": qc_path.as_posix(),
                "measurement_qc_file_sha256": artifact_sha256(qc_path),
                "measurement_qc_result_sha256": feature.source_qc_sha256,
            }
        )
    inputs_path = tmp_path / "inputs.json"
    inputs_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "analysis_scope_id": scope.analysis_scope_id,
                "data_origin": "simulated",
                "dataset_role": "software_validation",
                "measurements": measurements,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    output_root = tmp_path / "outputs"

    exit_code = run_dataset_quality_cli(
        [
            "--config",
            str(PROJECT_ROOT / "config" / "default.yaml"),
            "--scope",
            str(scope_path),
            "--inputs",
            str(inputs_path),
            "--output-root",
            str(output_root),
            "--run-id",
            "DEV-C6-CLI",
        ],
        project_root=PROJECT_ROOT,
    )

    assert exit_code == 0
    output = (
        output_root
        / "simulated"
        / "software_validation"
        / "DEV-C6-CLI"
        / "dataset_qc"
    )
    assert (output / "dataset_qc.json").is_file()
    manifest = json.loads(
        (output / "dataset_qc_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["processing_status"] == "completed"
    assert len(manifest["inputs"]) == 8
    assert {item["sample_id"] for item in manifest["inputs"]} == {
        "__dataset__",
        "cli-cont-01",
        "cli-cont-02",
    }

    tampered_inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
    tampered_inputs["measurements"][0]["feature_npz_sha256"] = "0" * 64
    inputs_path.write_text(
        json.dumps(tampered_inputs, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    failure_exit_code = run_dataset_quality_cli(
        [
            "--config",
            str(PROJECT_ROOT / "config" / "default.yaml"),
            "--scope",
            str(scope_path),
            "--inputs",
            str(inputs_path),
            "--output-root",
            str(output_root),
            "--run-id",
            "DEV-C6-CLI-FAIL",
        ],
        project_root=PROJECT_ROOT,
    )

    assert failure_exit_code == 1
    failure_output = (
        output_root
        / "simulated"
        / "software_validation"
        / "DEV-C6-CLI-FAIL"
        / "dataset_qc"
    )
    failure_manifest = json.loads(
        (failure_output / "dataset_qc_manifest.json").read_text(encoding="utf-8")
    )
    assert failure_manifest["processing_status"] == "failed"
    assert failure_manifest["success"] is False
    assert failure_manifest["failure"]["exception_type"] == "DatasetQCInputError"
    assert "hash mismatch" in failure_manifest["failure"]["message"]
    assert not (failure_output / "dataset_qc.json").exists()
