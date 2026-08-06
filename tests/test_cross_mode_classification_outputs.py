from __future__ import annotations

import json

import pytest

from acoustic_encoder.cross_mode_classification import analyze_cross_mode_classification
from acoustic_encoder.cross_mode_classification_outputs import (
    load_cross_mode_classification_bundle,
    write_cross_mode_classification_outputs,
)

from test_cross_mode_classification import _fixture


def test_cross_mode_outputs_are_complete_hashed_and_round_trip(tmp_path) -> None:
    artifacts, scope, p2b, comparison, config = _fixture()
    result = analyze_cross_mode_classification(
        artifacts, scope, config, dataset_qc_result=p2b, comparison_bundle=comparison
    )
    output = tmp_path / "classification"

    write_cross_mode_classification_outputs(
        result,
        scope,
        output,
        provenance={"data_origin": "simulated", "run_purpose": "software_validation"},
        input_artifacts=(),
        versions={"pipeline": "test"},
    )

    expected = {
        "protocol_scope_audit.csv", "cross_mode_group_audit.csv", "fold_assignments.csv",
        "training_composition.csv", "compatibility_audit.csv", "cross_mode_predictions.csv",
        "protocol_fold_metrics.csv", "protocol_summary.csv", "transfer_gap.csv",
        "per_class_metrics.csv", "confusion_matrices.csv", "difficult_direction_pairs.csv",
        "feature_mask_audit.csv", "training_transform_audit.csv", "classification_result.json",
        "classification_manifest.json", "classification_manifest.sha256",
    }
    assert expected <= {path.name for path in output.iterdir()}
    loaded = load_cross_mode_classification_bundle(output)
    assert loaded["result"] == result.to_dict()
    assert loaded["manifest"]["success"] is True
    assert loaded["manifest"]["provenance"]["scientifically_eligible"] is False
    manifest = json.loads((output / "classification_manifest.json").read_text(encoding="utf-8"))
    assert all(item["sha256"].startswith("sha256:") for item in manifest["artifacts"])

    with pytest.raises(FileExistsError, match="already exists"):
        write_cross_mode_classification_outputs(
            result, scope, output, provenance={}, input_artifacts=(), versions={}
        )
