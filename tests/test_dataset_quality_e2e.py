from __future__ import annotations

import json
from pathlib import Path

from acoustic_encoder.dataset_quality_validation import (
    run_simulated_dataset_quality_validation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_p2b_simulated_validation_writes_all_required_views(tmp_path: Path) -> None:
    validation = run_simulated_dataset_quality_validation(
        project_root=PROJECT_ROOT,
        config_path=PROJECT_ROOT / "config" / "validation_dev_c6_dataset_qc.yaml",
        output_root=tmp_path / "outputs",
        run_id="DEV-C6-E2E",
        feature_count=11,
    )

    result = validation.result
    assert len(result.scoped_sample_ids) == 32
    assert all(
        item.expected_count == item.observed_count
        and item.missing_count == 0
        and item.duplicate_count == 0
        and item.unexpected_count == 0
        for item in result.condition_results
    )
    assert {item.repeat_type for item in result.repeatability_results} == {
        "CONT",
        "REPOS",
        "REASM",
    }
    assert result.data_origin.value == "simulated"
    assert result.run_purpose.value == "software_validation"
    assert result.scientifically_eligible is False
    assert {
        "dataset_qc_summary.csv",
        "condition_completeness.csv",
        "same_condition_outliers.csv",
        "repeatability_qc.csv",
        "measurement_qc_rollup.csv",
        "manual_review_queue.csv",
        "dataset_qc.json",
        "dataset_qc_manifest.json",
        "dataset_qc_manifest.sha256",
    }.issubset(path.name for path in validation.output_directory.iterdir())
    manifest = json.loads(
        (validation.output_directory / "dataset_qc_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["processing_status"] == "completed"
    assert len(manifest["inputs"]) == 98
    assert len(manifest["artifacts"]) == 7
