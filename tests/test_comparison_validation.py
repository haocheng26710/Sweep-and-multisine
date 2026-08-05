from __future__ import annotations

import csv
import json

from acoustic_encoder.comparison_metrics_outputs import load_comparison_metrics_bundle
from acoustic_encoder.comparison_validation import run_simulated_comparison_validation

from test_comparison_metrics_outputs import PROJECT_ROOT


def test_full_simulated_p4b_validation_is_complete_but_not_scientific(tmp_path) -> None:
    output = run_simulated_comparison_validation(
        project_root=PROJECT_ROOT,
        output_root=tmp_path / "outputs",
        run_id="DEV-C7-validation",
        feature_count=21,
    )
    loaded = load_comparison_metrics_bundle(output)
    result = loaded["result"]
    assert result["processing_status"] == "completed_with_unavailable"
    assert result["canonical_analysis"] is False
    assert result["scientifically_eligible"] is False
    assert result["dataset_qc_link_status"] == "not_provided"
    assert result["cross_mode_metrics"]["common_tone_count"] == 21
    assert len(result["weighted_metrics"]) == 8
    with (output / "per_tone_bias.csv").open(encoding="utf-8", newline="") as handle:
        bias = list(csv.DictReader(handle))
    assert float(bias[0]["mean_bias_db"]) == -0.25
    assert float(bias[-1]["mean_bias_db"]) == 0.75
    manifest = json.loads((output / "metrics_manifest.json").read_text(encoding="utf-8"))
    assert manifest["success"] is False
    assert manifest["provenance"] == {
        "data_origin": "simulated",
        "run_purpose": "software_validation",
        "scientifically_eligible": False,
    }
