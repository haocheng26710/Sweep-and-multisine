from __future__ import annotations

import json
from pathlib import Path

import pytest

from acoustic_encoder.classification_outputs import load_classification_bundle
from acoustic_encoder.classification_cli import run_classification_cli
from acoustic_encoder.classification_validation import run_simulated_classification_validation
from acoustic_encoder.schemas import FeatureKind


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "feature_kind",
    [FeatureKind.DENSE_DEMEANED_DB, FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE],
)
def test_formal_classification_validation_is_separate_by_mode_and_not_scientific(tmp_path, feature_kind) -> None:
    output = run_simulated_classification_validation(
        project_root=PROJECT_ROOT,
        output_root=tmp_path / "outputs",
        run_id=f"DEV-C8-{feature_kind.value}",
        feature_kind=feature_kind,
    )

    bundle = load_classification_bundle(output)
    assert bundle["result"]["processing_status"] == "completed"
    assert bundle["result"]["canonical_analysis"] is True
    assert bundle["result"]["scientifically_eligible"] is False
    manifest = json.loads((output / "classification_manifest.json").read_text(encoding="utf-8"))
    assert manifest["provenance"] == {
        "data_origin": "simulated",
        "run_purpose": "software_validation",
        "scientifically_eligible": False,
    }


def test_cli_input_hash_mismatch_writes_failure_manifest_without_success(tmp_path) -> None:
    output_root = tmp_path / "outputs"
    output = run_simulated_classification_validation(
        project_root=PROJECT_ROOT,
        output_root=output_root,
        run_id="DEV-C8-good",
        feature_kind=FeatureKind.DENSE_DEMEANED_DB,
    )
    manifest = json.loads((output / "classification_manifest.json").read_text(encoding="utf-8"))
    by_role = {item["artifact_role"]: Path(item["path"]) for item in manifest["input_artifacts"] if item["artifact_id"].startswith("__")}
    inputs = json.loads(by_role["classification_input_manifest"].read_text(encoding="utf-8"))
    inputs["features"][0]["feature_npz_sha256"] = "0" * 64
    bad_inputs = tmp_path / "bad-inputs.json"
    bad_inputs.write_text(json.dumps(inputs), encoding="utf-8")
    dataset_qc_dir = by_role["dataset_qc_manifest"].parent

    status = run_classification_cli(
        (
            "--config", str(PROJECT_ROOT / "config" / "validation_dev_c8_classification.yaml"),
            "--scope", str(by_role["classification_scope"]),
            "--inputs", str(bad_inputs),
            "--dataset-qc-dir", str(dataset_qc_dir),
            "--output-root", str(output_root),
            "--run-id", "DEV-C8-bad-hash",
        ),
        project_root=PROJECT_ROOT,
    )

    assert status == 1
    failure = json.loads((output_root / "simulated" / "software_validation" / "DEV-C8-bad-hash" / "classification" / "classification_manifest.json").read_text(encoding="utf-8"))
    assert failure["success"] is False
    assert failure["processing_status"] == "failed"
    assert "hash mismatch" in failure["failure"]["message"]
