from __future__ import annotations

import json
import pytest

from acoustic_encoder.classification import analyze_classification_feature_sets
from acoustic_encoder.classification_outputs import (
    load_classification_bundle,
    write_classification_outputs,
)

from test_classification import _classification_fixture


def test_classification_outputs_are_complete_hashed_and_round_trip(tmp_path) -> None:
    artifacts, scope, p2b, config = _classification_fixture()
    result = analyze_classification_feature_sets(
        artifacts, scope, config, dataset_qc_result=p2b
    )
    output = tmp_path / "classification"

    write_classification_outputs(
        result,
        output,
        provenance={
            "data_origin": "simulated",
            "run_purpose": "software_validation",
            "scientifically_eligible": False,
        },
        input_artifacts=(),
        versions={"pipeline": "test", "config": "test", "measurement": "test", "feature": "test"},
    )
    loaded = load_classification_bundle(output)

    assert loaded["result"] == result.to_dict()
    expected = {
        "split_audit.csv", "fold_assignments.csv", "predictions.csv",
        "fold_metrics.csv", "aggregate_metrics.csv", "per_class_metrics.csv",
        "confusion_matrix.csv", "difficult_direction_pairs.csv",
        "feature_mask_audit.csv", "training_transform_audit.csv",
        "model_parameters.csv", "classification_result.json",
        "classification_manifest.json", "classification_manifest.json.sha256",
    }
    assert expected <= {item.name for item in output.iterdir()}
    manifest = json.loads((output / "classification_manifest.json").read_text(encoding="utf-8"))
    assert manifest["success"] is True
    assert manifest["provenance"]["scientifically_eligible"] is False


def test_classification_output_directory_refuses_overwrite(tmp_path) -> None:
    artifacts, scope, p2b, config = _classification_fixture()
    result = analyze_classification_feature_sets(artifacts, scope, config, dataset_qc_result=p2b)
    output = tmp_path / "classification"
    write_classification_outputs(result, output, provenance={}, input_artifacts=(), versions={})
    with pytest.raises(FileExistsError, match="already exists"):
        write_classification_outputs(result, output, provenance={}, input_artifacts=(), versions={})


def test_classification_bundle_detects_artifact_tampering(tmp_path) -> None:
    artifacts, scope, p2b, config = _classification_fixture()
    result = analyze_classification_feature_sets(artifacts, scope, config, dataset_qc_result=p2b)
    output = tmp_path / "classification"
    write_classification_outputs(result, output, provenance={}, input_artifacts=(), versions={})
    with (output / "predictions.csv").open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        load_classification_bundle(output)
